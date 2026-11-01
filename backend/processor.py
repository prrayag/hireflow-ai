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
    Env switches:
      HIREFLOW_USE_SPARK=0        skip Spark and use the Python fallback
      HIREFLOW_SPARK_MEMORY=512m  driver heap (Spark needs at least ~450m)
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

    if os.getenv("HIREFLOW_USE_SPARK", "1") == "0":
        _spark_available = False
        print("[HireFlow] Spark disabled via HIREFLOW_USE_SPARK=0 (Python mode).")
        return None

    try:
        conf = SparkConf() \
            .setAppName("HireFlow_Resume_Pipeline") \
            .setMaster("local[*]") \
            .set("spark.ui.enabled", "true") \
            .set("spark.ui.port", "4040") \
            .set("spark.ui.showConsoleProgress", "true") \
            .set("spark.driver.memory", os.getenv("HIREFLOW_SPARK_MEMORY", "512m")) \
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


# ─── Semantic Skill Matching ────────────────────────────────────────────────────
import json
import numpy as np
from numpy.linalg import norm
from skill_catalog import canonical

_skill_embeddings = None

def load_skill_embeddings():
    """Load pre-computed skill embeddings from skills.json"""
    global _skill_embeddings
    if _skill_embeddings is None:
        try:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skills.json')
            with open(path, 'r') as f:
                skills_data = json.load(f)
                # Convert lists back to numpy arrays
                _skill_embeddings = {k: np.array(v) for k, v in skills_data.items()}
                print(f"[HireFlow] Loaded {len(_skill_embeddings)} skill embeddings")
        except FileNotFoundError:
            print("[HireFlow] ⚠️  skills.json not found. Run: python generate_skills.py")
            _skill_embeddings = {}
    return _skill_embeddings


def find_similar_skill(extracted_skill, threshold=0.75):
    """
    Find semantically similar skill from our knowledge base.

    Examples:
        - Input: "django"  → Output: "Django"
        - Input: "fastapi" → Output: "FastAPI"
        - Input: "aws" → Output: "AWS"
        - Input: "kubernetes" → Output: "Kubernetes"
    """
    if not extracted_skill or not extracted_skill.strip():
        return None

    skill_embeddings = load_skill_embeddings()
    if not skill_embeddings:
        return extracted_skill

    extracted_skill_clean = extracted_skill.strip()

    # Check for exact match first (case-insensitive)
    for known_skill in skill_embeddings.keys():
        if known_skill.lower() == extracted_skill_clean.lower():
            return canonical(known_skill)

    try:
        # Get embedding for extracted skill
        extracted_vec = np.array(get_embedding(extracted_skill_clean))

        best_match = extracted_skill_clean
        best_score = 0.0

        # Find most similar skill
        for known_skill, skill_vec in skill_embeddings.items():
            # Cosine similarity
            dot_product = np.dot(extracted_vec, skill_vec)
            norm_extracted = norm(extracted_vec)
            norm_skill = norm(skill_vec)

            if norm_extracted > 0 and norm_skill > 0:
                similarity = dot_product / (norm_extracted * norm_skill)

                if similarity > best_score and similarity > threshold:
                    best_score = similarity
                    best_match = known_skill

        if best_score > threshold:
            print(f"[HireFlow] Matched '{extracted_skill}' -> '{best_match}' (score: {best_score:.3f})")
            return canonical(best_match)
        else:
            # No good match found, return original
            return extracted_skill_clean

    except Exception as e:
        print(f"[HireFlow] Error matching skill '{extracted_skill}': {e}")
        return extracted_skill_clean

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


# ─── Feature 3: Resume Summary (extractive, embedding-based) ───────────────────
def _split_sentences(text, max_sentences=80):
    """Sentence-like lines of a resume: 40-300 chars, no contact details."""
    import re
    parts = re.split(r'\n+|(?<=[.!?])\s+', text)
    sentences = []
    for part in parts:
        s = part.strip(" \t•·●▪◦*-–—")
        if not 40 <= len(s) <= 300 or len(s.split()) < 6:
            continue
        if '@' in s or re.search(r'\d{5,}', s):
            continue  # contact details
        if len(re.findall(r'[•·●▪◦|]', s)) >= 2 or s.count(',') >= 4:
            continue  # skill lists
        if re.search(r'\b(19|20)\d{2}\)?\s*$', s):
            continue  # education / date lines such as "B.Tech ... , 2018"
        sentences.append(s)
    return sentences[:max_sentences]


def generate_resume_summary(text, jd_text="", max_sentences=3):
    """
    Extractive summary: the resume sentences most similar to the job description
    (cosine similarity of Sentence-BERT embeddings), kept in their original order.
    Without a JD it picks the sentences closest to the resume's overall meaning.
    Nothing is generated, so every word comes from the resume itself.
    """
    sentences = [s if s[-1] in '.!?' else s + '.' for s in _split_sentences(text)]
    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    vectors = np.array(get_embedding(sentences))
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    if jd_text and jd_text.strip():
        query = np.array(get_embedding(jd_text))
    else:
        query = vectors.mean(axis=0)
    query = query / np.linalg.norm(query)

    scores = vectors @ query
    top = sorted(int(i) for i in np.argsort(-scores)[:max_sentences])
    return " ".join(sentences[i] for i in top)


# ─── Feature 2: Gap Analysis ────────────────────────────────────────────────────
_skill_context_embeddings = None
SIMILAR_SKILL_THRESHOLD = 0.55

def _load_skill_context_embeddings():
    """Load context-aware skill embeddings (see generate_skill_context.py)."""
    global _skill_context_embeddings
    if _skill_context_embeddings is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skill_context.json')
        try:
            with open(path, 'r') as f:
                _skill_context_embeddings = {k: np.array(v) for k, v in json.load(f).items()}
        except FileNotFoundError:
            print("[HireFlow] skill_context.json not found. Run: python generate_skill_context.py")
            _skill_context_embeddings = {}
    return _skill_context_embeddings


def find_similar_candidate_skills(missing_skills, candidate_skills, threshold=SIMILAR_SKILL_THRESHOLD):
    """
    For each skill the JD requires but the candidate lacks, find the most similar
    skill the candidate does have, using embedding cosine similarity.

    Returns: [{"required": "FastAPI", "has": "Flask", "score": 0.58}, ...]
    """
    embeddings = _load_skill_context_embeddings()
    if not embeddings or not missing_skills or not candidate_skills:
        return []

    candidates = [c for c in set(candidate_skills) if c in embeddings]
    similar = []
    for required in missing_skills:
        if required not in embeddings:
            continue
        req_vec = embeddings[required]
        best_skill, best_score = None, 0.0
        for have in candidates:
            have_vec = embeddings[have]
            score = float(np.dot(req_vec, have_vec) / (norm(req_vec) * norm(have_vec)))
            if score > best_score:
                best_skill, best_score = have, score
        if best_skill is not None and best_score >= threshold:
            similar.append({"required": required, "has": best_skill, "score": round(best_score, 2)})
    return similar


def create_gap_analysis(jd_text, candidate_skills):
    """
    Compare Job Description required skills with candidate's skills.
    Shows recruiter exactly which skills candidate HAS vs. MISSING.

    Returns:
    {
        "matched_skills": ["Python", "Docker"],
        "missing_skills": ["Kubernetes", "AWS"],
        "match_count": 2,
        "missing_count": 2,
        "match_percentage": 50.0,
        "total_required": 4,
        "status": "medium_match"  # strong_match | medium_match | weak_match
    }
    """
    # Skills the JD asks for: same extractor as for resumes (whole-word + embeddings)
    from skill_extractor import extract_skills
    jd_required_skills = extract_skills(jd_text)["skills"]

    # Remove duplicates and normalize
    jd_required_skills = sorted(list(set(jd_required_skills)))

    # Compare with candidate skills
    candidate_skills_set = set(candidate_skills) if candidate_skills else set()
    jd_required_skills_set = set(jd_required_skills)

    matched = list(candidate_skills_set & jd_required_skills_set)
    missing = list(jd_required_skills_set - candidate_skills_set)

    # Sort alphabetically for consistency
    matched = sorted(matched)
    missing = sorted(missing)

    match_percentage = 0
    if jd_required_skills:
        match_percentage = (len(matched) / len(jd_required_skills)) * 100

    # DL step: for each missing skill, look for a similar skill the candidate has
    similar_skills = find_similar_candidate_skills(missing, candidate_skills)
    with_similar_pct = 0
    if jd_required_skills:
        # Each similar skill counts in proportion to its similarity score (not as a full match)
        similarity_credit = sum(s["score"] for s in similar_skills)
        with_similar_pct = ((len(matched) + similarity_credit) / len(jd_required_skills)) * 100

    # Determine status
    if match_percentage >= 70:
        status = "strong_match"
    elif match_percentage >= 40:
        status = "medium_match"
    else:
        status = "weak_match"

    gap_analysis = {
        "matched_skills": matched,
        "missing_skills": missing,
        "match_count": len(matched),
        "missing_count": len(missing),
        "match_percentage": round(match_percentage, 1),
        "total_required": len(jd_required_skills),
        "similar_skills": similar_skills,
        "match_percentage_with_similar": round(with_similar_pct, 1),
        "status": status
    }

    return gap_analysis
