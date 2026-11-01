"""Two-stage neural retrieval and reranking for HireFlow AI."""

from __future__ import annotations

import os
from collections import defaultdict

import numpy as np
from pymongo import MongoClient
from pyspark import SparkConf
from pyspark.sql import SparkSession

from dl_pipeline import experience_match, process_resume_record, sentence_chunks, skill_gap

os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
os.environ.setdefault("HF_HOME", os.path.join(os.path.dirname(__file__), ".model_cache"))

BI_ENCODER_MODEL = os.getenv("BI_ENCODER_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
CROSS_ENCODER_MODEL = os.getenv("CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
ENABLE_CROSS_ENCODER = os.getenv("ENABLE_CROSS_ENCODER", "true").lower() in {"1", "true", "yes"}
MODEL_VERSION = "hireflow-neural-ranker-v1"


def _is_model_cached(model_name: str) -> bool:
    cache_name = "models--" + model_name.replace("/", "--")
    return os.path.isdir(os.path.join(os.environ["HF_HOME"], "hub", cache_name))

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    client.server_info()
    db = client["hireflow_db"]
    collection = db["resumes"]
except Exception as exc:
    print(f"[HireFlow] MongoDB connection warning: {exc}. Using in-memory fallback storage.")
    client = None
    collection = None

mock_db_storage: list[dict] = []
_spark = None
_spark_available = None
_bi_encoder = None
_cross_encoder = None
_cross_encoder_unavailable = False


def get_spark():
    global _spark, _spark_available
    if _spark_available is False:
        return None
    if _spark is not None:
        return _spark
    try:
        conf = (SparkConf().setAppName("HireFlow_Resume_Pipeline").setMaster("local[*]")
                .set("spark.ui.enabled", "true").set("spark.ui.port", "4040")
                .set("spark.driver.memory", "512m").set("spark.sql.shuffle.partitions", "8")
                .set("spark.default.parallelism", "8"))
        _spark = SparkSession.builder.config(conf=conf).getOrCreate()
        _spark.sparkContext.setLogLevel("WARN")
        _spark_available = True
        print("[HireFlow] Spark UI available at http://localhost:4040")
        return _spark
    except Exception as exc:
        _spark_available, _spark = False, None
        print(f"[HireFlow] Spark unavailable: {exc}\n[HireFlow] Running in Python mode.")
        return None


def _process_single_resume(resume: dict) -> list[dict]:
    return process_resume_record(resume)


def chunk_text(text: str, chunk_size: int = 90) -> list[str]:
    """Compatibility wrapper for older callers."""
    return [chunk["text"] for chunk in sentence_chunks(text, max_words=chunk_size)]


def _get_bi_encoder():
    global _bi_encoder
    if _bi_encoder is None:
        from sentence_transformers import SentenceTransformer
        print(f"[HireFlow] Loading bi-encoder: {BI_ENCODER_MODEL}")
        _bi_encoder = SentenceTransformer(
            BI_ENCODER_MODEL, local_files_only=_is_model_cached(BI_ENCODER_MODEL)
        )
    return _bi_encoder


def get_embedding(text: str) -> list[float]:
    return _get_bi_encoder().encode(text, normalize_embeddings=True).tolist()


def _encode_batch(texts: list[str]) -> np.ndarray:
    return np.asarray(_get_bi_encoder().encode(
        texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False
    ))


def _get_cross_encoder():
    global _cross_encoder, _cross_encoder_unavailable
    if not ENABLE_CROSS_ENCODER or _cross_encoder_unavailable:
        return None
    if _cross_encoder is None:
        try:
            from sentence_transformers import CrossEncoder
            print(f"[HireFlow] Loading cross-encoder: {CROSS_ENCODER_MODEL}")
            _cross_encoder = CrossEncoder(
                CROSS_ENCODER_MODEL, max_length=512,
                local_files_only=_is_model_cached(CROSS_ENCODER_MODEL),
            )
        except Exception as exc:
            _cross_encoder_unavailable = True
            print(f"[HireFlow] Cross-encoder unavailable; using bi-encoder fallback: {exc}")
    return _cross_encoder


def process_resumes_batch(resumes_data: list[dict]) -> int:
    """Create section-aware chunks, batch-embed them, and persist their vectors."""
    spark = get_spark()
    if spark is not None and len(resumes_data) >= 8:
        try:
            partitions = min(max(2, len(resumes_data) // 10), 16)
            # Spark workers start with their own sys.path. Ship the pure
            # preprocessing module explicitly so functions can be unpickled.
            spark.sparkContext.addPyFile(os.path.join(os.path.dirname(__file__), "dl_pipeline.py"))
            chunks = (spark.sparkContext.parallelize(resumes_data, partitions)
                      .flatMap(process_resume_record).collect())
            print(f"[HireFlow] Spark produced {len(chunks)} chunks across {partitions} partitions")
        except Exception as exc:
            # Ranking must remain available even when Java/Spark is unhealthy.
            print(f"[HireFlow] Spark batch failed; using local preprocessing: {exc}")
            chunks = [chunk for resume in resumes_data for chunk in process_resume_record(resume)]
    else:
        chunks = [chunk for resume in resumes_data for chunk in process_resume_record(resume)]
    if not chunks:
        return 0

    embeddings = _encode_batch([chunk["chunk_text"] for chunk in chunks])
    for chunk, embedding in zip(chunks, embeddings):
        chunk["embedding"] = embedding.tolist()
        chunk["model_version"] = MODEL_VERSION

    global mock_db_storage
    try:
        if collection is not None:
            collection.insert_many(chunks, ordered=False)
        else:
            mock_db_storage.extend(chunks)
    except Exception as exc:
        print(f"[HireFlow] MongoDB insert failed, using memory: {exc}")
        mock_db_storage.extend(chunks)
    return len(chunks)


def _load_chunks(resume_ids: set[str] | None) -> list[dict]:
    try:
        if collection is not None:
            query = {"embedding": {"$exists": True}}
            if resume_ids:
                query["resume_id"] = {"$in": list(resume_ids)}
            return list(collection.find(query, {"_id": 0}))
    except Exception as exc:
        print(f"[HireFlow] MongoDB read failed, using memory: {exc}")
    return [c for c in mock_db_storage if not resume_ids or c.get("resume_id") in resume_ids]


def search_best_candidates(jd_text: str, top_k: int = 5, resume_ids=None) -> list[dict]:
    """Retrieve with a bi-encoder, then rerank candidates with a cross-encoder."""
    ids = set(resume_ids) if resume_ids else None
    chunks = _load_chunks(ids)
    if not chunks:
        return []
    jd_vector = np.asarray(get_embedding(jd_text))
    grouped: dict[str, list[tuple[float, dict]]] = defaultdict(list)
    for chunk in chunks:
        embedding = np.asarray(chunk.get("embedding", []), dtype=float)
        if embedding.shape != jd_vector.shape:
            continue
        denom = np.linalg.norm(embedding) * np.linalg.norm(jd_vector)
        similarity = float(np.dot(jd_vector, embedding) / denom) if denom else 0.0
        grouped[chunk["resume_id"]].append((max(0.0, similarity), chunk))

    candidates = []
    for resume_id, scored_chunks in grouped.items():
        scored_chunks.sort(key=lambda item: item[0], reverse=True)
        top_chunks = scored_chunks[:3]
        best = top_chunks[0][1]
        semantic = 0.65 * top_chunks[0][0] + 0.35 * np.mean([x[0] for x in top_chunks])
        evidence = [item[1]["chunk_text"] for item in top_chunks]
        candidates.append({"resume_id": resume_id, "metadata": best.get("metadata", {}),
                           "semantic_score": float(semantic * 100), "evidence": evidence,
                           "reranker_text": " ".join(evidence)})
    candidates.sort(key=lambda item: item["semantic_score"], reverse=True)
    candidates = candidates[:max(top_k * 3, top_k)]

    cross_encoder = _get_cross_encoder()
    if cross_encoder and candidates:
        try:
            logits = np.asarray(cross_encoder.predict(
                [(jd_text, c["reranker_text"]) for c in candidates], show_progress_bar=False
            ), dtype=float).reshape(-1)
            probabilities = 1.0 / (1.0 + np.exp(-np.clip(logits, -30, 30)))
            for candidate, probability in zip(candidates, probabilities):
                candidate["reranker_score"] = float(probability * 100)
        except Exception as exc:
            print(f"[HireFlow] Cross-encoder inference failed: {exc}")

    results = []
    for candidate in candidates:
        meta = candidate["metadata"]
        gap = skill_gap(meta.get("skills", []), jd_text)
        exp_score = experience_match(meta.get("experience", 0), jd_text)
        reranker = candidate.get("reranker_score")
        if reranker is None:
            final = 0.80 * candidate["semantic_score"] + 0.15 * gap["skill_coverage"] + 0.05 * exp_score
            inference_mode = "bi-encoder-fallback"
        else:
            final = (0.45 * candidate["semantic_score"] + 0.40 * reranker
                     + 0.10 * gap["skill_coverage"] + 0.05 * exp_score)
            inference_mode = "bi-encoder+cross-encoder"
        results.append({
            "resume_id": candidate["resume_id"], "name": meta.get("name", "Unknown"),
            "ai_score": round(float(np.clip(final, 0, 100)), 2),
            "semantic_score": round(candidate["semantic_score"], 2),
            "reranker_score": round(reranker, 2) if reranker is not None else None,
            "skill_coverage": gap["skill_coverage"], "experience_match": round(exp_score, 2),
            "matched_skills": gap["matched_skills"], "missing_skills": gap["missing_skills"],
            "relevant_sentences": candidate["evidence"], "inference_mode": inference_mode,
            "model_version": MODEL_VERSION, "experience": meta.get("experience", 0),
            "skills": meta.get("skills", []), "email": meta.get("email", "Not Found"),
            "phone": meta.get("phone", "Not Found"), "education": meta.get("education", "Not Found"),
        })
    return sorted(results, key=lambda item: item["ai_score"], reverse=True)[:top_k]
