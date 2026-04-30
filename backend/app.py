# app.py - main Flask backend for HireFlow AI
<<<<<<< HEAD
# handles file uploads, resume parsing, and returning ranked results
# 
# We removed PySpark/HDFS references completely.
# Files are now processed sequentially with a ThreadPoolExecutor for basic parallelism.
# Files are saved locally to backend/uploads/.
# TODO: replace with real S3 upload when AWS is configured
=======
# this handles file uploads, resume parsing, and returning ranked results
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02

import os
import zipfile
import shutil
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS
from resume_parser import parse_resume, ALL_SUPPORTED_EXTENSIONS
from candidate_scorer import score_candidate, rank_candidates, detect_anomalies
from json_storage import save_to_json, load_json_data

app = Flask(__name__)
<<<<<<< HEAD
CORS(app)  # lets our React frontend talk to Flask without CORS errors

# folders for uploaded zips and extracted resumes
if os.environ.get("VERCEL"):
    UPLOAD_FOLDER  = "/tmp/uploads"
    EXTRACT_FOLDER = "/tmp/extracted"
else:
    UPLOAD_FOLDER  = os.path.join(os.path.dirname(__file__), "uploads")
    EXTRACT_FOLDER = os.path.join(os.path.dirname(__file__), "extracted")

os.makedirs(UPLOAD_FOLDER,  exist_ok=True)
os.makedirs(EXTRACT_FOLDER, exist_ok=True)


=======
CORS(app)  # this lets our React frontend talk to Flask without CORS errors

# folders for storing uploaded zips and extracted resumes
if os.environ.get("VERCEL"):
    UPLOAD_FOLDER = "/tmp/uploads"
    EXTRACT_FOLDER = "/tmp/extracted"
else:
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
    EXTRACT_FOLDER = os.path.join(os.path.dirname(__file__), "extracted")

# make sure the folders exist when the app starts
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXTRACT_FOLDER, exist_ok=True)

>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
def is_supported_file(filename):
    """Check if a file has a supported extension for resume parsing."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALL_SUPPORTED_EXTENSIONS

<<<<<<< HEAD

def process_extracted_files(folder_path, job_description=""):
    """
    Walk through a folder and parse + score every supported resume file.
    Uses a simple thread pool internally (no Spark needed).
    """
    parsed_and_scored = []

    # collect all valid file paths first
    file_paths = []
=======
def process_extracted_files(folder_path):
    """Walk through a folder and parse every supported resume file."""
    parsed_resumes = []
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
    for root, dirs, files in os.walk(folder_path):
        for fname in files:
            if fname.startswith(".") or fname.startswith("__"):
                continue
            if not is_supported_file(fname):
                print(f"skipping unsupported file: {fname}")
                continue
<<<<<<< HEAD
            file_paths.append(os.path.join(root, fname))

    # process each file (parse then score)
    # we keep this simple and sequential for reliability
    # in a production setup this would fan out to a worker queue
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def parse_and_score_one(filepath):
        try:
            result = parse_resume(filepath)
            if result is None:
                return None
            result["filename"] = os.path.basename(filepath)
            scored = score_candidate(result, job_description)
            return scored
        except Exception as e:
            print(f"failed to process {os.path.basename(filepath)}: {e}")
            return None

    max_workers = min(4, max(len(file_paths), 1))
    print(f"processing {len(file_paths)} resume(s) with {max_workers} thread(s)...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(parse_and_score_one, fp): fp for fp in file_paths}
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                parsed_and_scored.append(result)
                print(f"  done: {result.get('filename', '?')} -> score {result.get('score', '?')}")

    return parsed_and_scored

=======
            filepath = os.path.join(root, fname)
            print(f"parsing: {fname}")
            result = parse_resume(filepath)
            if result is not None:
                parsed_resumes.append(result)
    return parsed_resumes
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02

@app.route("/upload", methods=["POST"])
def upload_resumes():
    """
<<<<<<< HEAD
    Accepts resumes as ZIP file or multiple individual files.
    Parses, scores via TabTransformer hybrid pipeline, and returns ranked JSON.
    """
    job_description = request.form.get("job_description", "")

    has_zip   = "file" in request.files and request.files["file"].filename.endswith(".zip")
=======
    Accepts resumes in two modes: ZIP file or multiple individual files.
    Parses, scores using ML, and returns ranked results as JSON.
    """
    job_description = request.form.get("job_description", "")

    has_zip = "file" in request.files and request.files["file"].filename.endswith(".zip")
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
    has_files = "files" in request.files

    if not has_zip and not has_files:
        if "file" in request.files:
            single_file = request.files["file"]
            if single_file.filename and is_supported_file(single_file.filename):
                has_files = True
                request.files = {"files": single_file}
            else:
                return jsonify({"error": "No supported files uploaded. Please upload PDF, DOCX, DOC, or image files."}), 400
        else:
            return jsonify({"error": "No file was uploaded."}), 400

    try:
<<<<<<< HEAD
        # clear old extracted files
=======
        # clear out any old extracted files
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
        if os.path.exists(EXTRACT_FOLDER):
            shutil.rmtree(EXTRACT_FOLDER)
        os.makedirs(EXTRACT_FOLDER, exist_ok=True)

<<<<<<< HEAD
        if has_zip:
            # === ZIP MODE ===
            file = request.files["file"]
            print(f"received ZIP file: {file.filename}")

            # save ZIP to local uploads folder
            # TODO: replace with real S3 upload when AWS is configured
            zip_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(zip_path)
            print(f"saved ZIP to: {zip_path}")

            print("extracting ZIP...")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(EXTRACT_FOLDER)

=======
        parsed_resumes = []

        if has_zip:
            # === ZIP MODE ===
            file = request.files["file"]
            print(f"got a ZIP file: {file.filename}, starting to process...")

            zip_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(zip_path)

            print("unzipping the file...")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(EXTRACT_FOLDER)

            parsed_resumes = process_extracted_files(EXTRACT_FOLDER)

>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
        else:
            # === MULTI-FILE MODE ===
            files = request.files.getlist("files")
            if not files:
                single = request.files.get("files")
                files = [single] if single else []

<<<<<<< HEAD
            print(f"received {len(files)} individual file(s)")
=======
            print(f"got {len(files)} individual file(s), starting to process...")
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02

            for f in files:
                if not f or not f.filename:
                    continue
                if not is_supported_file(f.filename):
                    continue
<<<<<<< HEAD
                # save with a unique prefix to avoid collisions
=======

>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
                safe_name = f"{uuid.uuid4().hex[:8]}_{f.filename}"
                filepath = os.path.join(EXTRACT_FOLDER, safe_name)
                f.save(filepath)
                print(f"saved: {f.filename} -> {safe_name}")

<<<<<<< HEAD
        # process all extracted/saved files
        scored_candidates = process_extracted_files(EXTRACT_FOLDER, job_description)

        if len(scored_candidates) == 0:
            return jsonify({"error": "No valid resume files found."}), 400

        # rank by score
        ranked_candidates = rank_candidates(scored_candidates)

        # unique ID for this batch
        batch_id = str(uuid.uuid4())

        # save to JSON (preserves raw_text for future training/analysis)
        save_to_json(ranked_candidates, batch_id, job_description)

        # run anomaly detection (strips raw_text from each candidate)
        ranked_candidates = detect_anomalies(ranked_candidates)

        print(f"done! ranked {len(ranked_candidates)} candidates, batch_id={batch_id}")

        return jsonify({
            "message":         f"successfully processed {len(ranked_candidates)} resumes",
            "batch_id":        batch_id,
            "count":           len(ranked_candidates),
            "candidates":      ranked_candidates,
=======
                result = parse_resume(filepath)
                if result is not None:
                    result["filename"] = f.filename
                    parsed_resumes.append(result)

        if len(parsed_resumes) == 0:
            return jsonify({"error": "No valid resume files found."}), 400

        print(f"parsed {len(parsed_resumes)} resumes, now scoring...")

        # Score each parsed resume
        scored_candidates = []
        for resume_data in parsed_resumes:
            scored = score_candidate(resume_data, job_description)
            scored_candidates.append(scored)

        # Rank by score highest first
        ranked_candidates = rank_candidates(scored_candidates)

        # Generate unique batch ID
        batch_id = str(uuid.uuid4())

        # Save to JSON data lake FIRST (preserves raw_text for future ML training)
        save_to_json(ranked_candidates, batch_id, job_description)

        # Run anomaly detection (Keyword stuffing check - strips raw_text)
        ranked_candidates = detect_anomalies(ranked_candidates)

        print(f"done! ranked and saved {len(ranked_candidates)} candidates under batch {batch_id}")

        return jsonify({
            "message": f"successfully processed {len(ranked_candidates)} resumes",
            "batch_id": batch_id,
            "count": len(ranked_candidates),
            "candidates": ranked_candidates,
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
            "job_description": job_description
        }), 200

    except zipfile.BadZipFile:
        return jsonify({"error": "the uploaded file is not a valid ZIP"}), 400
    except Exception as e:
<<<<<<< HEAD
        print(f"upload error: {e}")
=======
        print(f"something went wrong: {e}")
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
        return jsonify({"error": f"server error: {str(e)}"}), 500


@app.route("/results", methods=["GET"])
def get_results():
<<<<<<< HEAD
    """Returns the latest batch of processed results from JSON storage."""
=======
    """
    Returns the latest batch of processed results directly from the JSON.
    """
    # Fetch from json instead of DB since DB is removed
>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
    data = load_json_data()
    latest_results = []
    job_description = ""
    if data and data.get("batches"):
<<<<<<< HEAD
        latest_batch    = data["batches"][-1]
        latest_results  = latest_batch["candidates"]
        job_description = latest_batch.get("job_description", "")

    return jsonify({
        "candidates":      latest_results,
        "count":           len(latest_results),
        "job_description": job_description
    }), 200


@app.route("/json-data", methods=["GET"])
def get_json_data():
    """Returns the full JSON storage data (all batches)."""
    data = load_json_data()
    return jsonify(data), 200


@app.route("/api/big-data-stats", methods=["GET"])
def big_data_stats():
    """
    Calculates aggregate metrics for the latest upload batch.
    Used by the dashboard charts (radar, scatter, pie).
    """
    import re as _re
    data = load_json_data()
    if not data or not data.get("batches"):
        return jsonify({"skills": [], "scatter": [], "anomalies": []}), 200

    # only use the LATEST batch so charts reflect current upload
    latest_batch = data["batches"][-1]
    candidates   = latest_batch.get("candidates", [])

    if not candidates:
        return jsonify({"skills": [], "scatter": [], "anomalies": []}), 200

    # 1. Skill frequency for Radar Chart
    skill_counts = {}
    for c in candidates:
        # support both old 'matched_skills' and new 'skills' fields
        skills = c.get("skills", []) or c.get("matched_skills", [])
        if not skills and "extracted_features" in c:
            skills = c["extracted_features"].get("matched_skills", [])
        for s in skills:
            skill_counts[s] = skill_counts.get(s, 0) + 1

    if skill_counts:
        skills_formatted = [
            {"subject": k, "A": v, "fullMark": max(skill_counts.values())}
            for k, v in skill_counts.items()
        ]
        skills_formatted = sorted(skills_formatted, key=lambda x: x["A"], reverse=True)[:5]
    else:
        skills_formatted = []

    # 2. Scatter plot: Experience vs Score
    experience_scatter = []
    for c in candidates:
        exp_years = c.get("experience_years", 0) or 0
        if exp_years == 0:
            raw_text = c.get("raw_text", "")
            if raw_text:
                match = _re.search(r'(\d+)\s*\+?\s*years?\s*(of\s+)?(experience)?', raw_text.lower())
                if match:
                    exp_years = min(int(match.group(1)), 30)

        experience_scatter.append({
            "name":       c.get("name", "Unknown"),
            "score":      c.get("score", 0),
            "experience": exp_years,
            "is_anomaly": c.get("is_anomaly", False)
        })

    # 3. Anomaly ratio for Pie Chart
    anomaly_count  = sum(1 for c in candidates if c.get("is_anomaly", False))
    normal_count   = len(candidates) - anomaly_count
    anomalies_data = [
        {"name": "Normal Resumes", "value": normal_count},
        {"name": "Anomalies",      "value": anomaly_count}
    ]

    return jsonify({
        "skills":          skills_formatted,
        "scatter":         experience_scatter,
        "anomalies":       anomalies_data,
        "total_in_batch":  len(candidates)
    }), 200


=======
        latest_batch = data["batches"][-1]
        latest_results = latest_batch["candidates"]
        job_description = latest_batch.get("job_description", "")
    
    return jsonify({
        "candidates": latest_results,
        "count": len(latest_results),
        "job_description": job_description
    }), 200

@app.route("/json-data", methods=["GET"])
def get_json_data():
    """
    Returns the full JSON storage data (all batches).
    """
    data = load_json_data()
    return jsonify(data), 200

>>>>>>> bc841b2b73539cb57fa7e01542fc93fa4bd72e02
if __name__ == "__main__":
    print("starting HireFlow AI backend on http://localhost:5001")
    app.run(debug=True, port=5001)
