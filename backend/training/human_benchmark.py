"""Human-judged ranking benchmark (10 resumes x 3 job descriptions = 30 pairs).

Step 1 - build the labelling sheet:
    backend/venv/bin/python backend/training/human_benchmark.py prepare

Step 2 - two team members independently fill annotator_1 / annotator_2 in
    backend/training/human_benchmark/labels.csv with 0-3 (see GUIDE.md).

Step 3 - score the system against the human labels:
    backend/venv/bin/python backend/training/human_benchmark.py evaluate

The evaluation reports inter-annotator agreement (quadratic-weighted Cohen's
kappa), Precision@3 / NDCG@5 / MRR / Spearman for each scoring component, and
an ablation of the full ranking with NER skill extraction vs dictionary only.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
import zipfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "training"))
os.environ.setdefault("HF_HOME", str(BACKEND_DIR / ".model_cache"))

from common import JOB_PROFILES, ranking_metrics  # noqa: E402

BENCHMARK_DIR = BACKEND_DIR / "training" / "human_benchmark"
RESULTS_DIR = BACKEND_DIR / "training" / "results"
DEFAULT_JDS = ("backend_python", "frontend", "devops")
LABEL_COLUMNS = ("annotator_1", "annotator_2")
SCORE_KEYS = {
    "full_system": "ai_score",
    "bi_encoder_only": "semantic_score",
    "cross_encoder_only": "reranker_score",
    "skill_coverage_only": "skill_coverage",
}

GUIDE = """# Ranking benchmark - labelling guide

Score every resume against every job description in `labels.csv`, working
**independently** (do not discuss scores until both of you have finished).
Read the job description in `jds.json` and the resume text in `resumes/`.

| Score | Meaning |
|---|---|
| 3 | Excellent - would shortlist immediately; meets nearly all requirements |
| 2 | Good - meets the core requirements, some gaps |
| 1 | Weak - a few relevant skills, but not a real fit |
| 0 | Poor - not relevant to this role |

Rules:
- Judge the candidate, not the formatting. Ignore names, gender, age and location.
- Fill `annotator_1` (first person) and `annotator_2` (second person) with 0, 1, 2 or 3.
- Use `notes` for anything unclear. Do not look at the system's scores first.
"""


def _resume_files(source: Path) -> list[tuple[str, bytes]]:
    if source.suffix == ".zip":
        with zipfile.ZipFile(source) as archive:
            return [(Path(info.filename).name, archive.read(info)) for info in archive.infolist()
                    if not info.is_dir() and not info.filename.startswith("__MACOSX")
                    and info.filename.lower().endswith((".pdf", ".docx", ".txt"))]
    return [(path.name, path.read_bytes()) for path in sorted(source.iterdir())
            if path.suffix.lower() in {".pdf", ".docx", ".txt"}]


def prepare(args) -> None:
    from resume_parser import process_file_content
    files = sorted(_resume_files(args.resumes))
    if len(files) < args.count:
        raise SystemExit(f"Need at least {args.count} resumes in {args.resumes}")
    chosen = sorted(random.Random(args.seed).sample(files, args.count))
    profiles = {p["jd_id"]: p for p in JOB_PROFILES}
    jds = [{"jd_id": jd_id, "title": profiles[jd_id]["title"], "text": profiles[jd_id]["text"]}
           for jd_id in args.jd_ids]

    out = args.out
    (out / "resumes").mkdir(parents=True, exist_ok=True)
    resumes = []
    for filename, data in chosen:
        resume_id = Path(filename).stem
        text = process_file_content(filename, data)
        (out / "resumes" / f"{resume_id}.txt").write_text(text, encoding="utf-8")
        resumes.append({"resume_id": resume_id, "resume_file": filename})
    (out / "jds.json").write_text(json.dumps(jds, indent=2), encoding="utf-8")
    (out / "GUIDE.md").write_text(GUIDE, encoding="utf-8")
    labels_path = out / "labels.csv"
    if labels_path.exists() and not args.force:
        raise SystemExit(f"{labels_path} already exists; pass --force to overwrite it.")
    with labels_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["pair_id", "jd_id", "jd_title", "resume_id", *LABEL_COLUMNS, "notes"])
        pair = 1
        for jd in jds:
            for resume in resumes:
                writer.writerow([pair, jd["jd_id"], jd["title"], resume["resume_id"], "", "", ""])
                pair += 1
    (out / "manifest.json").write_text(json.dumps({
        "source": str(args.resumes.relative_to(REPO_DIR) if args.resumes.is_relative_to(REPO_DIR) else args.resumes),
        "seed": args.seed, "resumes": resumes, "jd_ids": list(args.jd_ids),
    }, indent=2), encoding="utf-8")
    print(f"Wrote {pair - 1} pairs to {labels_path}. Fill annotator_1 and annotator_2, then run "
          f"`human_benchmark.py evaluate`.")


def quadratic_weighted_kappa(a: list[int], b: list[int], categories: int = 4) -> float:
    """Cohen's kappa with quadratic weights for ordinal 0..categories-1 labels."""
    n = len(a)
    if n == 0:
        return 0.0
    observed = [[0.0] * categories for _ in range(categories)]
    for x, y in zip(a, b):
        observed[x][y] += 1
    hist_a = [sum(row) for row in observed]
    hist_b = [sum(observed[i][j] for i in range(categories)) for j in range(categories)]
    numerator = denominator = 0.0
    for i in range(categories):
        for j in range(categories):
            weight = (i - j) ** 2 / (categories - 1) ** 2
            numerator += weight * observed[i][j]
            denominator += weight * hist_a[i] * hist_b[j] / n
    return 1.0 - numerator / denominator if denominator else 1.0


def read_labels(path: Path) -> tuple[list[dict], dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    used = [c for c in LABEL_COLUMNS if all(r[c].strip() for r in rows)]
    partial = [c for c in LABEL_COLUMNS if c not in used and any(r[c].strip() for r in rows)]
    if not used or partial:
        raise SystemExit(f"{path}: every row needs a 0-3 score in {', '.join(partial or LABEL_COLUMNS)}.")
    for row in rows:
        for column in used:
            if row[column].strip() not in {"0", "1", "2", "3"}:
                raise SystemExit(f"pair {row['pair_id']}: {column} must be 0, 1, 2 or 3")
        row["label"] = sum(int(row[c]) for c in used) / len(used)
    agreement = {"annotators": len(used)}
    if len(used) == 2:
        a = [int(r[used[0]]) for r in rows]
        b = [int(r[used[1]]) for r in rows]
        agreement.update({
            "exact_agreement": round(sum(x == y for x, y in zip(a, b)) / len(rows), 4),
            "within_one": round(sum(abs(x - y) <= 1 for x, y in zip(a, b)) / len(rows), 4),
            "quadratic_weighted_kappa": round(quadratic_weighted_kappa(a, b), 4),
        })
    return rows, agreement


def _set_ner(enabled: bool) -> None:
    import ner_parser
    with ner_parser._lock:
        ner_parser._tagger, ner_parser._tagger_loaded = None, not enabled
    if enabled:
        ner_parser.get_tagger()


def system_scores(rows: list[dict], benchmark_dir: Path, use_ner: bool) -> dict[tuple[str, str], dict]:
    """Rank the benchmark resumes with the real pipeline, kept in memory (no Mongo writes)."""
    import processor
    from resume_parser import extract_metadata
    processor.collection = None          # use the in-memory store
    processor.get_spark = lambda: None   # 10 resumes do not need a Spark cluster
    _set_ner(use_ner)
    prefix = "ner" if use_ner else "dict"
    resume_ids = sorted({r["resume_id"] for r in rows})
    batch = []
    for resume_id in resume_ids:
        text = (benchmark_dir / "resumes" / f"{resume_id}.txt").read_text(encoding="utf-8")
        meta = extract_metadata(text)
        batch.append({"resume_id": f"{prefix}:{resume_id}", "name": resume_id, "text": text,
                      **{k: meta[k] for k in ("email", "phone", "education", "skills", "experience",
                                              "ner_only_skills", "soft_skills", "skill_parser")}})
    processor.process_resumes_batch(batch)
    jds = {jd["jd_id"]: jd for jd in json.loads((benchmark_dir / "jds.json").read_text(encoding="utf-8"))}
    scores = {}
    for jd_id in sorted({r["jd_id"] for r in rows}):
        ranked = processor.search_best_candidates(jds[jd_id]["text"], top_k=len(batch),
                                                  resume_ids=[r["resume_id"] for r in batch])
        for result in ranked:
            scores[(jd_id, result["resume_id"].split(":", 1)[1])] = result
    return scores


def evaluate(args) -> None:
    from scipy.stats import spearmanr
    rows, agreement = read_labels(args.labels)
    report = {"pairs": len(rows), "resumes": len({r["resume_id"] for r in rows}),
              "job_descriptions": len({r["jd_id"] for r in rows}), "agreement": agreement,
              "relevance_threshold": "mean human label >= 2", "runs": {}}
    for run_name, use_ner in (("with_ner", True), ("dictionary_only", False)):
        scored = system_scores(rows, args.benchmark_dir, use_ner)
        run = {}
        for method, key in SCORE_KEYS.items():
            method_rows = []
            for row in rows:
                result = scored.get((row["jd_id"], row["resume_id"]), {})
                value = result.get(key)
                method_rows.append({"jd_id": row["jd_id"], "label": row["label"],
                                    "score": float(value) if value is not None else 0.0})
            metrics = ranking_metrics(method_rows, "score")
            metrics["spearman_vs_humans"] = round(float(spearmanr(
                [r["score"] for r in method_rows], [r["label"] for r in method_rows]).statistic), 4)
            run[method] = metrics
        report["runs"][run_name] = run
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    args.output.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
    print(markdown(report))


def markdown(report: dict) -> str:
    agreement = report["agreement"]
    lines = ["# Human ranking benchmark", "",
             f"{report['pairs']} resume-JD pairs ({report['resumes']} resumes x "
             f"{report['job_descriptions']} job descriptions), {agreement['annotators']} annotator(s).", ""]
    if agreement["annotators"] == 2:
        lines += [f"Inter-annotator agreement: exact {agreement['exact_agreement']:.0%}, "
                  f"within one point {agreement['within_one']:.0%}, quadratic-weighted kappa "
                  f"{agreement['quadratic_weighted_kappa']:.3f}.", ""]
    for run_name, run in report["runs"].items():
        title = {"with_ner": "With NER skill extraction", "dictionary_only": "Dictionary skills only"}
        lines += [f"## {title.get(run_name, run_name)}", "",
                  "| Scoring | P@3 | R@5 | NDCG@5 | MRR | Spearman vs humans |",
                  "|---|---:|---:|---:|---:|---:|"]
        for method, m in run.items():
            lines.append(f"| {method} | {m['precision_at_3']:.3f} | {m['recall_at_5']:.3f} | "
                         f"{m['ndcg_at_5']:.3f} | {m['mrr']:.3f} | {m['spearman_vs_humans']:.3f} |")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare", help="build the labelling sheet")
    p.add_argument("--resumes", type=Path, default=REPO_DIR / "100_resumes.zip",
                   help="zip file or folder of PDF/DOCX/TXT resumes")
    p.add_argument("--count", type=int, default=10)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--jd-ids", nargs="+", default=list(DEFAULT_JDS))
    p.add_argument("--out", type=Path, default=BENCHMARK_DIR)
    p.add_argument("--force", action="store_true")
    e = sub.add_parser("evaluate", help="score the system against the filled sheet")
    e.add_argument("--labels", type=Path, default=BENCHMARK_DIR / "labels.csv")
    e.add_argument("--benchmark-dir", type=Path, default=BENCHMARK_DIR)
    e.add_argument("--output", type=Path, default=RESULTS_DIR / "human_benchmark.json")
    args = parser.parse_args()
    prepare(args) if args.command == "prepare" else evaluate(args)


if __name__ == "__main__":
    main()
