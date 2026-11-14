"""OCR for image resumes, with a result cache and parallel processing.

EasyOCR on CPU takes about 15 s per image (about 19 s of that is the text recogniser, which
does not scale well across threads), and nothing in its settings changes that. So:

* results are cached by file hash, so re-uploading the same image is instant;
* the reader is loaded once and can be warmed up at server start;
* a batch of 3 or more new images is spread over several worker processes, because
  each process runs its own recogniser concurrently. Workers are plain subprocesses running
  this file (`python ocr_service.py --worker ...`), not a multiprocessing pool: on Windows a pool
  would re-import the Flask app, MongoDB and Spark in every worker.

Environment:
    OCR_WORKERS        most worker processes for a batch (default 4)
    OCR_PARALLEL_MIN   smallest number of new images that justifies the workers (default 3)
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor

MAX_WORKERS = int(os.getenv("OCR_WORKERS", "4"))
PARALLEL_MIN = int(os.getenv("OCR_PARALLEL_MIN", "3"))

_cache: dict[str, str] = {}
_reader = None
_lock = threading.Lock()


def _digest(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def get_reader():
    """The EasyOCR reader, created on first use. Loaded lazily to avoid a macOS fork crash with PyTorch."""
    global _reader
    if _reader is None:
        with _lock:
            if _reader is None:
                import easyocr
                _reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _reader


def _read(data: bytes) -> str:
    return " ".join(get_reader().readtext(data, detail=0))


def _run_worker(items: list[tuple[str, bytes]], threads: int) -> dict[str, str]:
    """OCR `items` in a separate Python process and return {hash: text}."""
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = os.path.join(tmp, "in.pkl"), os.path.join(tmp, "out.json")
        with open(src, "wb") as fh:
            pickle.dump(items, fh)
        env = {**os.environ, "OMP_NUM_THREADS": str(threads), "MKL_NUM_THREADS": str(threads)}
        subprocess.run([sys.executable, "-I", os.path.abspath(__file__), "--worker", src, dst, str(threads)],
                       check=True, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with open(dst, encoding="utf-8") as fh:
            return json.load(fh)


def prefetch(images: list[bytes]) -> None:
    """OCR all new images, in parallel when there are enough of them, and fill the cache."""
    new = {}
    for data in images:
        key = _digest(data)
        if key not in _cache and key not in new:
            new[key] = data
    if len(new) < PARALLEL_MIN:
        return  # ocr_image() will handle the few images one by one
    workers = max(2, min(len(new), MAX_WORKERS, (os.cpu_count() or 4) // 2))
    threads = max(1, (os.cpu_count() or 4) // workers // 2)
    items = list(new.items())
    shares = [items[i::workers] for i in range(workers)]  # round-robin so shares are even
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for result in pool.map(lambda share: _run_worker(share, threads), shares):
                _cache.update(result)
    except Exception as exc:  # fall back to the slow path rather than failing the upload
        print(f"[HireFlow] Parallel OCR failed, using one process: {exc}")


def ocr_image(data: bytes) -> str:
    key = _digest(data)
    if key not in _cache:
        _cache[key] = _read(data)
    return _cache[key]


if __name__ == "__main__":
    # Worker mode: python ocr_service.py --worker <input.pkl> <output.json> <threads>
    if len(sys.argv) == 5 and sys.argv[1] == "--worker":
        import torch
        torch.set_num_threads(int(sys.argv[4]))
        with open(sys.argv[2], "rb") as fh:
            work = pickle.load(fh)
        with open(sys.argv[3], "w", encoding="utf-8") as fh:
            json.dump({key: _read(data) for key, data in work}, fh)
