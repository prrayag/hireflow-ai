# app.py - main Flask backend for HireFlow AI
# handles file uploads, resume parsing, and returning ranked results
# 
# We removed PySpark/HDFS references completely.
# Files are now processed sequentially with a ThreadPoolExecutor for basic parallelism.
# Files are saved locally to backend/uploads/.
# TODO: replace with real S3 upload when AWS is configured

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
CORS(app)  # lets our React frontend talk to Flask without CORS errors

# ── MongoDB index bootstrap (run once on startup) ────────────────────────────
def _ensure_mongo_indexes():
    """Create indexes if they don't exist — runs once in background at startup."""
    try:
        from pymongo import MongoClient, DESCENDING
        from config import MONGO_URI
        if not MONGO_URI:
            return
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=4000)
        db = client["hireflow_db"]
        col = db["candidates"]
        col.create_index([("uploaded_at", DESCENDING)], background=True)
        col.create_index([("batch_id", DESCENDING)], background=True)
        print("[MongoDB] indexes ensured")
    except Exception as e:
        print(f"[MongoDB] index bootstrap skipped: {e}")

import threading as _threading
_threading.Thread(target=_ensure_mongo_indexes, daemon=True).start()

# folders for uploaded zips and extracted resumes
if os.environ.get("VERCEL"):
    UPLOAD_FOLDER  = "/tmp/uploads"
    EXTRACT_FOLDER = "/tmp/extracted"
else:
    UPLOAD_FOLDER  = os.path.join(os.path.dirname(__file__), "uploads")
    EXTRACT_FOLDER = os.path.join(os.path.dirname(__file__), "extracted")

os.makedirs(UPLOAD_FOLDER,  exist_ok=True)
os.makedirs(EXTRACT_FOLDER, exist_ok=True)


def is_supported_file(filename):
    """Check if a file has a supported extension for resume parsing."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALL_SUPPORTED_EXTENSIONS


def process_extracted_files(folder_path, job_description=""):
    """
    Walk through a folder and parse + score every supported resume file.
    Uses a simple thread pool internally (no Spark needed).
    """
    parsed_and_scored = []

    # collect all valid file paths first
    file_paths = []
    for root, dirs, files in os.walk(folder_path):
        for fname in files:
            if fname.startswith(".") or fname.startswith("__"):
                continue
            if not is_supported_file(fname):
                print(f"skipping unsupported file: {fname}")
                continue
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
                print(f"  done: {result.get('filename', '?')} → score {result.get('score', '?')}")

    return parsed_and_scored


@app.route("/upload", methods=["POST"])
def upload_resumes():
    """
    Accepts resumes as ZIP file or multiple individual files.
    Parses, scores via TabTransformer hybrid pipeline, and returns ranked JSON.
    """
    job_description = request.form.get("job_description", "")

    has_zip   = "file" in request.files and request.files["file"].filename.endswith(".zip")
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
        # clear old extracted files
        if os.path.exists(EXTRACT_FOLDER):
            shutil.rmtree(EXTRACT_FOLDER)
        os.makedirs(EXTRACT_FOLDER, exist_ok=True)

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

        else:
            # === MULTI-FILE MODE ===
            files = request.files.getlist("files")
            if not files:
                single = request.files.get("files")
                files = [single] if single else []

            print(f"received {len(files)} individual file(s)")

            for f in files:
                if not f or not f.filename:
                    continue
                if not is_supported_file(f.filename):
                    continue
                # save with a unique prefix to avoid collisions
                safe_name = f"{uuid.uuid4().hex[:8]}_{f.filename}"
                filepath = os.path.join(EXTRACT_FOLDER, safe_name)
                f.save(filepath)
                print(f"saved: {f.filename} → {safe_name}")

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
            "job_description": job_description
        }), 200

    except zipfile.BadZipFile:
        return jsonify({"error": "the uploaded file is not a valid ZIP"}), 400
    except Exception as e:
        print(f"upload error: {e}")
        return jsonify({"error": f"server error: {str(e)}"}), 500


@app.route("/results", methods=["GET"])
def get_results():
    """
    Returns the latest batch of processed results.
    Tries MongoDB first (full candidate list), falls back to local JSON.
    """
    from config import MONGO_URI

    # ── Try MongoDB ──────────────────────────────────────────────────────
    if MONGO_URI:
        try:
            from pymongo import MongoClient, DESCENDING
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
            col = client["hireflow_db"]["candidates"]

            # Get the most recent batch_id
            latest = col.find_one(
                {}, {"batch_id": 1}, sort=[("uploaded_at", DESCENDING)]
            )
            if latest:
                batch_id = latest["batch_id"]
                candidates = list(
                    col.find(
                        {"batch_id": batch_id},
                        {"_id": 0, "batch_id": 0, "uploaded_at": 0}
                    ).sort("rank", 1)
                )
                job_desc = candidates[0].get("job_description", "") if candidates else ""
                # strip job_description from each row (it's a batch field, not candidate field)
                for c in candidates:
                    c.pop("job_description", None)
                return jsonify({
                    "candidates":      candidates,
                    "count":           len(candidates),
                    "job_description": job_desc
                }), 200
        except Exception as e:
            print(f"[/results] MongoDB read failed, using JSON fallback: {e}")

    # ── JSON fallback ─────────────────────────────────────────────────────
    data = load_json_data()
    latest_results = []
    job_description = ""
    if data and data.get("batches"):
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
    Real-time analytics pulled from MongoDB Atlas (primary source).
    Falls back to local JSON if MongoDB is unavailable.
    Aggregates across ALL batches stored so data grows with every upload.
    """
    import re as _re
    from config import MONGO_URI

    candidates = []
    source = "json"

    # ── Try MongoDB first ────────────────────────────────────────────
    if MONGO_URI:
        try:
            from pymongo import MongoClient, DESCENDING
            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
            db     = client["hireflow_db"]
            col    = db["candidates"]
            # Projection: only fields we actually use in analytics (faster)
            projection = {
                "_id": 0, "score": 1, "skills": 1, "matched_skills": 1,
                "shortlisted": 1, "is_anomaly": 1, "name": 1,
                "job_role": 1, "department": 1
            }
            raw_docs = list(col.find({}, projection).limit(1000))
            if raw_docs:
                candidates = raw_docs
                source     = "mongodb"
                print(f"[big-data-stats] loaded {len(candidates)} docs from MongoDB")
        except Exception as e:
            print(f"[big-data-stats] MongoDB unavailable, using JSON fallback: {e}")

    # ── JSON fallback ────────────────────────────────────────────────
    if not candidates:
        data = load_json_data()
        if data and data.get("batches"):
            for batch in data["batches"]:
                candidates.extend(batch.get("candidates", []))

    if not candidates:
        return jsonify({
            "skills": [], "scatter": [], "anomalies": [],
            "histogram": [], "funnel": [], "heatmap": [],
            "gauge": {"avgScore": 0, "shortlistRate": 0, "anomalyRate": 0, "totalCandidates": 0},
            "radar": [], "source": source, "total_in_batch": 0
        }), 200

    # ── 1. Skill frequency → Radar / Spider chart ────────────────────
    skill_counts = {}
    for c in candidates:
        skills = c.get("skills", []) or c.get("matched_skills", [])
        for s in skills:
            s_lower = str(s).lower().strip()
            if s_lower:
                skill_counts[s_lower] = skill_counts.get(s_lower, 0) + 1

    top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:8]
    max_freq   = top_skills[0][1] if top_skills else 1
    radar_data = [
        {"subject": k.title(), "A": v, "fullMark": max_freq}
        for k, v in top_skills
    ]
    # also keep as horizontal bar data
    skills_bar = [{"subject": k.title(), "A": v, "fullMark": max_freq} for k, v in top_skills[:5]]

    # ── 2. Score Histogram — 10% bands ──────────────────────────────
    buckets = {f"{i*10}-{i*10+10}%": 0 for i in range(10)}
    for c in candidates:
        score     = float(c.get("score", 0) or 0)
        idx       = min(int(score // 10), 9)
        label     = f"{idx*10}-{idx*10+10}%"
        buckets[label] += 1
    histogram_data = [{"range": k, "count": v} for k, v in buckets.items()]   # keep 0s for full axis

    # ── 3. Hiring Funnel ────────────────────────────────────────────
    shortlisted  = [c for c in candidates if c.get("shortlisted")]
    high_score   = [c for c in candidates if float(c.get("score", 0) or 0) >= 50]
    no_anomaly   = [c for c in candidates if not c.get("is_anomaly", False)]
    funnel_data  = [
        {"stage": "Total Uploaded",  "count": len(candidates)},
        {"stage": "Parsed OK",       "count": len([c for c in candidates if c.get("name")])},
        {"stage": "Score ≥ 50%",     "count": len(high_score)},
        {"stage": "Shortlisted",     "count": len(shortlisted)},
        {"stage": "No Anomalies",    "count": len(no_anomaly)},
    ]

    # ── 4. Skill × Score Heatmap ─────────────────────────────────────
    skill_score_map = {}
    for c in candidates:
        score  = float(c.get("score", 0) or 0)
        skills = c.get("skills", []) or c.get("matched_skills", [])
        for s in skills[:6]:
            key = str(s).lower().strip()
            if key:
                skill_score_map.setdefault(key, []).append(score)

    heatmap_data = []
    for skill, scores in skill_score_map.items():
        heatmap_data.append({
            "skill":    skill.title(),
            "avgScore": round(sum(scores) / len(scores), 1),
            "count":    len(scores)
        })
    heatmap_data = sorted(heatmap_data, key=lambda x: x["avgScore"], reverse=True)[:12]

    # ── 5. Gauge metrics ─────────────────────────────────────────────
    all_scores     = [float(c.get("score", 0) or 0) for c in candidates]
    anomaly_count  = sum(1 for c in candidates if c.get("is_anomaly", False))
    avg_score      = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0
    shortlist_rate = round(len(shortlisted) / len(candidates) * 100, 1) if candidates else 0
    anomaly_rate   = round(anomaly_count   / len(candidates) * 100, 1) if candidates else 0
    gauge_data = {
        "avgScore":        avg_score,
        "shortlistRate":   shortlist_rate,
        "anomalyRate":     anomaly_rate,
        "totalCandidates": len(candidates),
    }

    # ── 6. Dataset meta (for Big Data metrics panel) ─────────────────
    import sys, os as _os
    json_path = _os.path.join(_os.path.dirname(__file__), "candidates_data.json")
    json_size_kb = round(_os.path.getsize(json_path) / 1024, 1) if _os.path.exists(json_path) else 0
    unique_roles  = len({c.get("job_role", "") for c in candidates if c.get("job_role")})
    unique_depts  = len({c.get("department", "") for c in candidates if c.get("department")})
    meta = {
        "totalRows":    len(candidates),
        "totalColumns": 14,         # fixed schema width
        "datasetKB":    json_size_kb,
        "uniqueRoles":  unique_roles,
        "uniqueDepts":  unique_depts,
        "source":       source,
    }

    return jsonify({
        "radar":          radar_data,
        "skills":         skills_bar,
        "histogram":      histogram_data,
        "funnel":         funnel_data,
        "heatmap":        heatmap_data,
        "gauge":          gauge_data,
        "meta":           meta,
        "source":         source,
        "total_in_batch": len(candidates),
    }), 200


if __name__ == "__main__":
    print("starting HireFlow AI backend on http://localhost:5001")
    app.run(debug=True, port=5001)

