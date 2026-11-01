"""Evaluate retrieval/reranking quality and simple name-swap fairness."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
from scipy.stats import spearmanr

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("HF_HOME", str(BACKEND_DIR / ".model_cache"))
from training.common import ranking_metrics, read_jsonl


def cross_logits(model, pairs: list[tuple[str, str]], batch_size: int = 16) -> np.ndarray:
    device = next(model.model.parameters()).device
    scores = []
    model.model.eval()
    with torch.no_grad():
        for start in range(0, len(pairs), batch_size):
            batch = pairs[start:start + batch_size]
            tokens = model.tokenizer([p[0] for p in batch], [p[1] for p in batch],
                                     padding=True, truncation=True, max_length=384,
                                     return_tensors="pt")
            tokens = {key: value.to(device) for key, value in tokens.items()}
            scores.extend(model.model(**tokens).logits.reshape(-1).cpu().numpy().tolist())
    return np.asarray(scores)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", type=Path, default=Path("backend/training/data/test.jsonl"))
    parser.add_argument("--fine-tuned", type=Path,
                        default=Path("backend/model_artifacts/cross_encoder_v1"))
    parser.add_argument("--output", type=Path,
                        default=Path("backend/training/results/evaluation.json"))
    args = parser.parse_args()
    rows = read_jsonl(args.test)
    pairs = [(row["jd_text"], row["resume_text"]) for row in rows]

    from sentence_transformers import CrossEncoder, SentenceTransformer
    bi = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    start = time.perf_counter()
    jd_vectors = bi.encode([row["jd_text"] for row in rows], normalize_embeddings=True,
                           batch_size=32, show_progress_bar=False)
    resume_vectors = bi.encode([row["resume_text"] for row in rows], normalize_embeddings=True,
                               batch_size=32, show_progress_bar=False)
    bi_scores = np.sum(jd_vectors * resume_vectors, axis=1)
    bi_seconds = time.perf_counter() - start

    models = {
        "pretrained_cross_encoder": CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", max_length=384),
    }
    if args.fine_tuned.exists():
        models["fine_tuned_cross_encoder"] = CrossEncoder(str(args.fine_tuned), max_length=384)

    for row, score in zip(rows, bi_scores):
        row["skill_baseline"] = row["skill_coverage"]
        row["bi_encoder"] = float(score)

    metrics = {
        "skill_baseline": ranking_metrics(rows, "skill_baseline"),
        "bi_encoder": {**ranking_metrics(rows, "bi_encoder"), "latency_seconds": round(bi_seconds, 4)},
    }
    fairness = {}
    for name, model in models.items():
        start = time.perf_counter()
        logits = cross_logits(model, pairs)
        latency = time.perf_counter() - start
        for row, score in zip(rows, logits):
            row[name] = float(score)
        metric = ranking_metrics(rows, name)
        metric["spearman_with_weak_labels"] = round(float(spearmanr(
            logits, [row["label"] for row in rows]).statistic), 4)
        metric["latency_seconds"] = round(latency, 4)
        metrics[name] = metric

        # Replace the first line (candidate name) without changing qualifications.
        neutral_pairs = [(row["jd_text"], "Candidate Name\n" + "\n".join(
            row["resume_text"].splitlines()[1:])) for row in rows]
        neutral_logits = cross_logits(model, neutral_pairs)
        original_prob = 1 / (1 + np.exp(-np.clip(logits, -30, 30)))
        neutral_prob = 1 / (1 + np.exp(-np.clip(neutral_logits, -30, 30)))
        deltas = np.abs(original_prob - neutral_prob) * 100
        fairness[name] = {"mean_name_mask_delta_points": round(float(np.mean(deltas)), 4),
                          "max_name_mask_delta_points": round(float(np.max(deltas)), 4)}

    report = {
        "warning": "Labels are synthetic skill-overlap labels, not human judgements.",
        "test_pairs": len(rows), "test_resumes": len({row["resume_id"] for row in rows}),
        "job_descriptions": len({row["jd_id"] for row in rows}),
        "metrics": metrics, "fairness": fairness,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
