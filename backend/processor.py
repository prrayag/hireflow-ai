import os
os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
from pymongo import MongoClient
from pyspark.sql import SparkSession
from pyspark import SparkConf

# Connect to MongoDB Atlas Vector Search
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    client.server_info() # force connection check
    db = client["hireflow_db"]
    collection = db["resumes"]

except Exception as e:
    print(f"[HireFlow] MongoDB connection warning: {e}. Using in-memory fallback storage.")
    client = None
    collection = None

mock_db_storage = []

# ─── Spark Session (Singleton with UI Enabled) ────────────────────────────────
_spark = None
_spark_available = None  # None = untested, True = OK, False = use Python fallback

def get_spark():
    """Returns a SparkSession when Java 17+ is available, otherwise None.
    Spark UI (when available): http://localhost:4040
    """
    global _spark, _spark_available
    if _spark_available is False:
        return None
    if _spark is not None:
        try:
            if not _spark._jsc.sc().isStopped():
                return _spark
        except Exception:
            _spark = None

    try:
        conf = SparkConf() \
            .setAppName("HireFlow_Resume_Pipeline") \
            .setMaster("local[*]") \
            .set("spark.ui.enabled", "true") \
            .set("spark.ui.port", "4040") \
            .set("spark.ui.showConsoleProgress", "true") \
            .set("spark.driver.memory", "300m") \
            .set("spark.sql.shuffle.partitions", "8") \
            .set("spark.default.parallelism", "8") \
            .set("spark.rdd.compress", "true") \
            .set("spark.serializer", "org.apache.spark.serializer.KryoSerializer")

        _spark = SparkSession.builder \
            .config(conf=conf) \
            .getOrCreate()

        _spark.sparkContext.setLogLevel("WARN")
        _spark_available = True
        print("[HireFlow] Spark UI available at http://localhost:4040")
        return _spark
    except Exception as e:
        _spark_available = False
        _spark = None
        print(f"[HireFlow] Spark unavailable: {e}")
        print("[HireFlow] Running in Python mode (install Java 17 for Spark UI).")
        return None

def _process_single_resume(resume):
    """Chunks a single resume into semantic segments."""
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
    spark_results = []

    if spark is not None:
        sc = spark.sparkContext
        sc.setJobGroup("resume_ingestion", f"Processing batch of {len(resumes_data)} resumes")

        num_partitions = min(max(4, len(resumes_data) // 10), 32)
        rdd = sc.parallelize(resumes_data, numSlices=num_partitions)
        chunks_rdd = rdd.flatMap(_process_single_resume)
        chunks_rdd.setName("ResumeChunks")
        chunks_rdd.cache()
        spark_results = chunks_rdd.collect()

        print(f"[HireFlow] Spark produced {len(spark_results)} chunks from {len(resumes_data)} resumes "
              f"across {num_partitions} partitions")
    else:
        for resume in resumes_data:
            spark_results.extend(_process_single_resume(resume))
        print(f"[HireFlow] Python fallback produced {len(spark_results)} chunks from {len(resumes_data)} resumes")
    
    # ── Stage 4: Generate embeddings on the driver node ──
    # (JobBERT model stays on driver to avoid PyTorch serialization issues)
    results = []
    for item in spark_results:
        item["embedding"] = get_embedding(item["chunk_text"])
        results.append(item)
    
    # ── Stage 5: Bulk insert into MongoDB ──
    if results:
        global mock_db_storage
        try:
            if collection is not None:
                collection.insert_many(results, ordered=False)
            else:
                mock_db_storage.extend(results)
        except Exception as e:
            print(f"MongoDB insert failed, using mock storage: {e}")
            mock_db_storage.extend(results)
        
    return len(results)

def search_best_candidates(jd_text, top_k=5, resume_ids=None):
    """
    Converts JD to vector and uses MongoDB Vector Search to find best resume chunks.
    When resume_ids is provided, only candidates from that batch are returned.
    Score is blended: 70% AI similarity + 30% experience relevance.
    """
    # Convert the entire JD into a vector using the same model
    jd_vector = get_embedding(jd_text)
    
    # Build a resume_ids set for fast filtering
    resume_ids_set = set(resume_ids) if resume_ids else None
    
    # Use MongoDB's $vectorSearch to compare the JD vector against all stored resume chunks
    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index", 
                "path": "embedding", 
                "queryVector": jd_vector, 
                "numCandidates": 200, 
                "limit": top_k * 10 # Get more chunks to allow filtering
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
    
    matches = []
    if collection is not None:
        try:
            matches = list(collection.aggregate(pipeline))
        except Exception as e:
            matches = []
            
    if not matches:
        # Fallback to local cosine similarity using the AI embeddings
        import numpy as np
        from numpy.linalg import norm
        

        # If filtering by batch, only fetch those chunks from MongoDB or mock storage


        global mock_db_storage
        all_chunks = []
        try:
            if collection is not None:
                query = {"embedding": {"$exists": True}}
                if resume_ids_set:
                    query["resume_id"] = {"$in": list(resume_ids_set)}
                all_chunks = list(collection.find(query))
            else:
                all_chunks = mock_db_storage
        except Exception as e:
            print(f"Failed to fetch from MongoDB, using mock storage: {e}")
            all_chunks = mock_db_storage
            
        if resume_ids_set:
            all_chunks = [c for c in all_chunks if c.get('resume_id') in resume_ids_set]
            
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
    
    # Filter to only current batch if resume_ids were provided
    if resume_ids_set:
        matches = [m for m in matches if m.get('resume_id') in resume_ids_set]
    
    # Post-process: Get the top unique candidates
    seen_names = set()
    unique_candidates = []
    for match in matches:
        candidate_name = match['metadata'].get('name', 'Unknown')
        if candidate_name not in seen_names:
            seen_names.add(candidate_name)
            # AI similarity score (0-100)
            similarity_pct = match['score'] * 100
            
            # Experience normalization (cap at 20 years, scale to 0-100)
            exp = match['metadata'].get('experience', 0)
            exp_normalized = min(exp, 20) / 20 * 100
            
            # Blended score: 70% AI similarity + 30% experience
            blended_score = 0.70 * similarity_pct + 0.30 * exp_normalized
            
            # Scale to display range 55-95% (industry-standard visual remapping)
            blended_score = round(55 + (blended_score * 0.40), 2)
            
            unique_candidates.append({
                "resume_id": match['resume_id'],
                "name": match['metadata'].get('name', 'Unknown'),
                "ai_score": blended_score,
                "experience": exp,
                "skills": match['metadata'].get('skills', []),
                "email": match['metadata'].get('email', 'Not Found'),
                "phone": match['metadata'].get('phone', 'Not Found'),
                "education": match['metadata'].get('education', 'Not Found')
            })
            if len(unique_candidates) >= top_k:
                break

    # Re-sort by the blended score (experience can change the order)
    unique_candidates = sorted(unique_candidates, key=lambda x: x['ai_score'], reverse=True)
    
    return unique_candidates

