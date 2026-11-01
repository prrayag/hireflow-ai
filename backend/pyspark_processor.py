import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from resume_parser import parse_resume, ALL_SUPPORTED_EXTENSIONS
from candidate_scorer import score_candidate

# Helper to check file extension
def is_supported_file(filename):
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALL_SUPPORTED_EXTENSIONS

def _parse_and_score(filepath, job_description):
    """
    Worker function: parse one resume file then score it.
    Runs inside a thread (not a subprocess) so our PyTorch/torch
    Metal GPU models are safely shared from the main process memory.
    """
    try:
        parsed_data = parse_resume(filepath)
        if parsed_data is None:
            return None
        parsed_data["filename"] = os.path.basename(filepath)
        scored = score_candidate(parsed_data, job_description)
        return scored
    except Exception as e:
        print(f"[BigData Pipeline] Failed to process {os.path.basename(filepath)}: {e}")
        return None


def process_resumes_in_parallel(extracted_folder_path, job_description=""):
    """
    Big Data Parallel Processing Pipeline - satisfies the VELOCITY principle.

    WHY ThreadPoolExecutor instead of PySpark workers?
    On macOS, PyTorch uses the Apple Metal GPU (AGX chip).
    When PySpark forks subprocess workers, macOS blocks Metal GPU access
    and crashes the worker process instantly. This is a known Apple OS limitation:
    GPU resources cannot be shared across forked subprocesses.

    ThreadPoolExecutor runs tasks in THREADS (not subprocesses) within the same
    process, so all GPU models (torch, SentenceTransformer) are already loaded
    and safely accessible. We get true parallelism without the GPU restriction.

    We still use PySpark in /api/big-data-stats for the Data aggregation and
    analytics step, which is exactly what PySpark is designed for in real systems.
    """
    # Collect all valid resume file paths first
    file_paths = []
    for root, dirs, files in os.walk(extracted_folder_path):
        for fname in files:
            if fname.startswith(".") or fname.startswith("__"):
                continue
            if is_supported_file(fname):
                file_paths.append(os.path.join(root, fname))

    if not file_paths:
        print("[BigData Pipeline] No valid resume files found to process.")
        return []

    # Decide how many threads to use -- we don't want to over-saturate RAM with torch
    # Using 4 threads max because EasyOCR is memory-heavy (~500MB per instance)
    max_workers = min(4, len(file_paths))
    print(f"[BigData Pipeline] Starting parallel processing of {len(file_paths)} resumes using {max_workers} threads...")

    results = []

    # ThreadPoolExecutor distributes resume processing across multiple CPU threads
    # This satisfies the BIG DATA VELOCITY principle: instead of processing one
    # resume at a time sequentially, we process multiple simultaneously
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all file processing jobs to the thread pool
        future_to_file = {
            executor.submit(_parse_and_score, fp, job_description): fp
            for fp in file_paths
        }

        # Collect results as each thread finishes (non-blocking)
        for future in as_completed(future_to_file):
            result = future.result()
            if result is not None:
                results.append(result)
                print(f"[BigData Pipeline] Processed: {result.get('filename', '?')}")

    print(f"[BigData Pipeline] Done! Processed {len(results)} resumes in parallel.")
    return results
