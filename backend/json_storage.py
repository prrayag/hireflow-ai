# json_storage.py - handles saving extracted resume data to JSON
# This JSON file serves as the primary data input for future ML model training
# and sorting/ranking logic. Every upload appends a new batch to this file.

import os
import json
import threading
from datetime import datetime
from pymongo import MongoClient
from config import MONGO_URI

# JSON file location — stored in the backend directory
JSON_FILE_PATH = os.path.join(os.path.dirname(__file__), "candidates_data.json")


def _save_to_mongo(batch_entry):
    """
    Background worker to push the batch entry to MongoDB Atlas.
    """
    if not MONGO_URI:
        return
        
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client['hireflow_db']
        collection = db['batches']
        
        # Copy the dictionary so we don't accidentally mutate the original data
        # with MongoDB's _id field.
        batch_copy = dict(batch_entry)
        collection.insert_one(batch_copy)
        print(f"successfully saved batch {batch_entry['batch_id']} to MongoDB Atlas!")
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


def save_to_json(candidates_list, batch_id, job_description=""):
    """
    Saves a batch of scored candidates to the JSON file.
    Each batch contains all candidate data from one upload session.
    
    This function APPENDS to the existing JSON file — it never overwrites
    previous batches. This is critical because the JSON acts as training
    data for the ML model.
    
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
        # (it's large and not needed for dashboard display)
        candidate_entry = {k: v for k, v in cand.items() if k != "raw_text"}
        # Ensure rank is always present
        candidate_entry.setdefault("rank", 0)
        batch_candidates.append(candidate_entry)
    
    # create the batch entry
    batch_entry = {
        "batch_id": batch_id,
        "uploaded_at": now,
        "job_description": job_description,
        "candidate_count": len(batch_candidates),
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
        
    # push to MongoDB Atlas in the background
    threading.Thread(target=_save_to_mongo, args=(batch_entry,)).start()
    
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
    Each entry has: name, raw_text, matched_skills, score, filename, etc.
    """
    data = _load_existing_data()
    all_resumes = []
    for batch in data.get("batches", []):
        for candidate in batch.get("candidates", []):
            # include batch context for the model
            candidate_with_context = {
                **candidate,
                "batch_id": batch["batch_id"],
                "job_description": batch.get("job_description", ""),
                "uploaded_at": batch.get("uploaded_at", "")
            }
            all_resumes.append(candidate_with_context)
    return all_resumes
