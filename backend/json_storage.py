# json_storage.py - handles saving extracted resume data to JSON
# This JSON file serves as the primary data input for future ML model training
# and sorting/ranking logic. Every upload appends a new batch to this file.
# Data is also pushed to MongoDB Atlas in the background for real-time storage.

import os
import json
import threading
from datetime import datetime
from pymongo import MongoClient
from config import MONGO_URI, MONGO_DB_NAME, MONGO_COLLECTION

# JSON file location — stored in the backend directory
JSON_FILE_PATH = os.path.join(os.path.dirname(__file__), "candidates_data.json")

# Current scoring pipeline version — tracked in each batch
SCORER_VERSION = "v2.0-composite"


def _save_to_mongo(batch_candidates, batch_id, job_description, uploaded_at):
    """
    Background worker to push individual candidate entries to MongoDB Atlas.
    """
    if not MONGO_URI:
        print("MongoDB connection skipped: MONGO_URI is not set in environment.")
        return
        
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client[MONGO_DB_NAME]
        collection = db[MONGO_COLLECTION]
        
        # Prepare documents for insertion by attaching batch metadata
        documents = []
        for cand in batch_candidates:
            doc = dict(cand)
            doc['batch_id'] = batch_id
            doc['job_description'] = job_description
            doc['uploaded_at'] = uploaded_at
            doc['scorer_version'] = SCORER_VERSION
            documents.append(doc)
            
        if documents:
            collection.insert_many(documents)
            print(f"successfully saved {len(documents)} individual candidates to MongoDB Atlas!")
    except Exception as e:
        print(f"error saving to MongoDB Atlas: {e}")


def _load_existing_data():
    """
    Load the existing JSON file if it exists.
    Returns the parsed data dict or a fresh skeleton if file doesn't exist.
    """
    if os.path.exists(JSON_FILE_PATH):
        try:
            with open(JSON_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except (json.JSONDecodeError, IOError) as e:
            print(f"warning: could not read existing JSON file, starting fresh: {e}")
    
    # return a fresh skeleton
    return {
        "last_updated": None,
        "total_batches": 0,
        "total_resumes": 0,
        "batches": []
    }


def _deduplicate_skills(skills_list):
    """
    Remove duplicate skills (case-insensitive) while preserving order.
    E.g., ['Python', 'python', 'PYTHON', 'Java'] -> ['Python', 'Java']
    """
    if not skills_list:
        return []
    seen = set()
    deduped = []
    for skill in skills_list:
        key = skill.strip().lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(skill.strip())
    return deduped


def save_to_json(candidates_list, batch_id, job_description=""):
    """
    Saves a batch of scored candidates to the JSON file.
    Each batch contains all candidate data from one upload session.
    
    This function APPENDS to the existing JSON file — it never overwrites
    previous batches. Deduplicates skills before saving.
    
    Args:
        candidates_list: list of candidate dicts (from the scorer)
        batch_id: unique UUID string for this upload batch
        job_description: the job description used for this batch (if any)
    """
    # load existing data
    data = _load_existing_data()
    
    now = datetime.now().isoformat()
    
    # build the candidate entries for this batch
    batch_candidates = []
    for cand in candidates_list:
        # Save every field the scorer returns — strip only the raw_text
        candidate_entry = {k: v for k, v in cand.items() if k != "raw_text"}
        
        # Deduplicate skills lists
        if "skills" in candidate_entry:
            candidate_entry["skills"] = _deduplicate_skills(candidate_entry["skills"])
        if "matched_skills" in candidate_entry:
            candidate_entry["matched_skills"] = _deduplicate_skills(candidate_entry["matched_skills"])
        
        # Ensure rank is always present
        candidate_entry.setdefault("rank", 0)
        batch_candidates.append(candidate_entry)
    
    # create the batch entry
    batch_entry = {
        "batch_id": batch_id,
        "uploaded_at": now,
        "job_description": job_description,
        "candidate_count": len(batch_candidates),
        "scorer_version": SCORER_VERSION,
        "candidates": batch_candidates
    }
    
    # append to the batches list
    data["batches"].append(batch_entry)
    data["last_updated"] = now
    data["total_batches"] = len(data["batches"])
    data["total_resumes"] = sum(b["candidate_count"] for b in data["batches"])
    
    # write back to file
    try:
        with open(JSON_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"saved batch {batch_id} to {JSON_FILE_PATH} ({len(batch_candidates)} candidates)")
    except IOError as e:
        print(f"error writing JSON file: {e}")
        raise e
        
    # push individual candidates to MongoDB Atlas in the background
    threading.Thread(target=_save_to_mongo, args=(batch_candidates, batch_id, job_description, now)).start()
    
    return JSON_FILE_PATH


def load_json_data():
    """
    Load and return the full JSON data.
    Used by the API endpoint and for future model training input.
    """
    return _load_existing_data()


def get_all_resumes_for_training():
    """
    Flattens all batches and returns a list of all resume entries.
    This is the format the ML model will consume for training.
    """
    data = _load_existing_data()
    all_resumes = []
    for batch in data.get("batches", []):
        for candidate in batch.get("candidates", []):
            candidate_with_context = {
                **candidate,
                "batch_id": batch["batch_id"],
                "job_description": batch.get("job_description", ""),
                "uploaded_at": batch.get("uploaded_at", "")
            }
            all_resumes.append(candidate_with_context)
    return all_resumes
