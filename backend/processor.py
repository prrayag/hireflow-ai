import os
os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
from pymongo import MongoClient
from pyspark.sql import SparkSession
from pyspark import SparkConf

# Connect to MongoDB Atlas Vector Search
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)
db = client["hireflow_db"]
collection = db["resumes"]

# ─── Spark Session (Singleton with UI Enabled) ────────────────────────────────
_spark = None

def get_spark():
    """Returns a persistent SparkSession with the Spark UI enabled on port 4040.
    The UI exposes DAGs, RDDs, stages, and executor metrics at http://localhost:4040
    """
    global _spark
    if _spark is None or _spark._jsc.sc().isStopped():
        conf = SparkConf() \
            .setAppName("HireFlow_Resume_Pipeline") \
            .setMaster("local[*]") \
            .set("spark.ui.enabled", "true") \
            .set("spark.ui.port", "4040") \
            .set("spark.ui.showConsoleProgress", "true") \
            .set("spark.driver.memory", "2g") \
            .set("spark.sql.shuffle.partitions", "8") \
            .set("spark.default.parallelism", "8") \
            .set("spark.rdd.compress", "true") \
            .set("spark.serializer", "org.apache.spark.serializer.KryoSerializer")

        _spark = SparkSession.builder \
            .config(conf=conf) \
            .getOrCreate()
        
        # Set log level to reduce noise but keep stage/task info
        _spark.sparkContext.setLogLevel("WARN")
        print(f"[HireFlow] Spark UI available at http://localhost:4040")
    
    return _spark

def chunk_text(text, chunk_size=20):
    """Splits text into chunks of approximately 20 words for Semantic Chunking."""
    words = text.split()
    chunks = [' '.join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
    return chunks

def get_embedding(text):
    """Converts text into a vector (embedding) using our JobBERT model."""
    global model
    if 'model' not in globals():
        from sentence_transformers import SentenceTransformer
        print("Loading JobBERT model...")
        model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2') 
    return model.encode(text).tolist()

def process_resumes_batch(resumes_data):
    """
    Parallel Processing Pipeline (Apache Spark):
    Takes raw OCR text from a batch of resumes and processes them using
    Spark RDDs for distributed chunking. The pipeline:
    1. Parallelizes resume data across Spark workers
    2. FlatMaps each resume into semantic chunks (RDD transformation)
    3. Collects results back to the driver
    4. Generates JobBERT embeddings on the driver (avoids PyTorch pickling)
    5. Bulk inserts into MongoDB for vector search
    
    resumes_data: list of dicts with {'resume_id', 'text', 'name', 'email', 'skills', 'experience'}
    """
    spark = get_spark()
    sc = spark.sparkContext
    
    # Set a descriptive job group so it shows up nicely in the Spark UI
    sc.setJobGroup("resume_ingestion", f"Processing batch of {len(resumes_data)} resumes")
    
    # ── Stage 1: Parallelize raw resume data into an RDD ──
    # The number of partitions scales with batch size for optimal parallelism
    num_partitions = min(max(4, len(resumes_data) // 10), 32)
    rdd = sc.parallelize(resumes_data, numSlices=num_partitions)
    
    def process_single_resume(resume):
        """Worker function: chunks a single resume into semantic segments."""
        text = resume.get('text', '')
        chunks = chunk_text(text, 20)
        
        processed_data = []
        for chunk in chunks:
            processed_data.append({
                "resume_id": resume.get("resume_id"),
                "chunk_text": chunk,
                "metadata": {
                    "name": resume.get("name", "Unknown"),
                    "email": resume.get("email", ""),
                    "phone": resume.get("phone", "Not Found"),
                    "education": resume.get("education", "Not Found"),
                    "skills": resume.get("skills", []),
                    "experience": resume.get("experience", 0)
                }
            })
        return processed_data
    
    # ── Stage 2: FlatMap transformation (visible as an RDD stage in Spark UI) ──
    chunks_rdd = rdd.flatMap(process_single_resume)
    
    # Cache the RDD so it persists in memory for the Spark UI to inspect
    chunks_rdd.setName("ResumeChunks")
    chunks_rdd.cache()
    
    # ── Stage 3: Collect to driver ──
    spark_results = chunks_rdd.collect()
    
    print(f"[HireFlow] Spark produced {len(spark_results)} chunks from {len(resumes_data)} resumes "
          f"across {num_partitions} partitions")
    
    # ── Stage 4: Generate embeddings on the driver node ──
    # (JobBERT model stays on driver to avoid PyTorch serialization issues)
    results = []
    for item in spark_results:
        item["embedding"] = get_embedding(item["chunk_text"])
        results.append(item)
    
    # ── Stage 5: Bulk insert into MongoDB ──
    if results:
        # Use ordered=False for parallel inserts on large batches
        collection.insert_many(results, ordered=False)
        
    return len(results)

def search_best_candidates(jd_text, top_k=5):
    """
    Converts JD to vector and uses MongoDB Vector Search to find best resume chunks.
    """
    # Convert the entire JD into a vector using the same model
    jd_vector = get_embedding(jd_text)
    
    # Use MongoDB's $vectorSearch to compare the JD vector against all stored resume chunks
    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index", 
                "path": "embedding", 
                "queryVector": jd_vector, 
                "numCandidates": 100, 
                "limit": top_k * 5 # Get more chunks to group by candidate
            }
        },
        {
            "$project": {
                "_id": 0,
                "resume_id": 1,
                "chunk_text": 1,
                "metadata": 1,
                "score": { "$meta": "vectorSearchScore" }
            }
        }
    ]
    
    try:
        matches = list(collection.aggregate(pipeline))
    except Exception as e:
        print(f"Vector search failed (index might not exist, computing locally): {e}")
        # Fallback to local cosine similarity using the AI embeddings
        import numpy as np
        from numpy.linalg import norm
        
        all_chunks = list(collection.find({"embedding": {"$exists": True}}))
        if not all_chunks:
            return []
            
        jd_v = np.array(jd_vector)
        norm_jd = norm(jd_v)
        if norm_jd == 0: norm_jd = 1e-9
        
        matches = []
        for chunk in all_chunks:
            emb = np.array(chunk['embedding'])
            norm_emb = norm(emb)
            if norm_emb == 0: norm_emb = 1e-9
            
            sim = np.dot(jd_v, emb) / (norm_jd * norm_emb)
            # Rescale similarity from [-1, 1] to [0, 1] for percentage
            sim_normalized = (sim + 1) / 2
            
            matches.append({
                "resume_id": chunk["resume_id"],
                "chunk_text": chunk["chunk_text"],
                "metadata": chunk["metadata"],
                "score": float(sim_normalized)
            })
            
        matches = sorted(matches, key=lambda x: x["score"], reverse=True)
    
    # Post-process: Get the top unique candidates
    seen_names = set()
    unique_candidates = []
    for match in matches:
        candidate_name = match['metadata'].get('name', 'Unknown')
        if candidate_name not in seen_names:
            seen_names.add(candidate_name)
            # Convert similarity score to a readable percentage format
            ai_score = round(match['score'] * 100, 2)
            unique_candidates.append({
                "resume_id": match['resume_id'],
                "name": match['metadata'].get('name', 'Unknown'),
                "ai_score": ai_score,
                "experience": match['metadata'].get('experience', 0),
                "skills": match['metadata'].get('skills', []),
                "email": match['metadata'].get('email', 'Not Found'),
                "phone": match['metadata'].get('phone', 'Not Found'),
                "education": match['metadata'].get('education', 'Not Found')
            })
            if len(unique_candidates) >= top_k:
                break
                
    return unique_candidates
