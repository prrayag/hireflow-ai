"""How much does the parser change the ranking?

The final score is 45% bi-encoder + 40% cross-encoder + 10% skill coverage + 5%
experience match. The two neural parts read the resume text, not the parser output,
so only the last two terms (15 points) depend on parsing. This script computes those
two terms from the gold labels (the "ideal"), from the regex parser and from the NER
parser, and reports how far each is from the ideal and whether it orders the
resumes the same way.

Usage (from backend/):
    python training/ner/ranking_impact.py [--group images|kaggle|template|all]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).parent))

import ner_parser  # noqa: E402
from dl_pipeline import experience_match, skill_gap  # noqa: E402
from evaluate_parsers import GOLD, canonical, group_of  # noqa: E402
from regex_parser import extract_metadata  # noqa: E402
from training.common import JOB_PROFILES  # noqa: E402

# Generic, non-technical JDs, because most gold resumes are not IT roles.
EXTRA_JDS = [
    {"jd_id": "manager_5y", "text": "Manager with 5+ years of experience leading teams and managing budgets."},
    {"jd_id": "specialist_3y", "text": "Specialist with 3 years of experience in the role. Strong communication."},
    {"jd_id": "senior_8y", "text": "Senior professional with 8+ years of experience and proven leadership."},
]


def ranks(values: list[float]) -> np.ndarray:
    order = np.argsort(values, kind="stable")
    r = np.empty(len(values))
    r[order] = np.arange(len(values))
    for v in set(values):  # average ranks for ties
        idx = [i for i, x in enumerate(values) if x == v]
        r[idx] = np.mean(r[idx])
    return r


def spearman(a: list[float], b: list[float]) -> float | None:
    ra, rb = ranks(a), ranks(b)
    if ra.std() == 0 or rb.std() == 0:
        return None  # one side is constant, so there is no ordering to compare
    return float(np.corrcoef(ra, rb)[0, 1])


def structured(skills: list[str], exp: float | None, jd: str) -> float:
    """The parser-dependent 15 points of the final score."""
    cov = skill_gap(skills, jd)["skill_coverage"]
    exp_term = experience_match(exp, jd) if exp is not None else 0.0
    return 0.10 * cov + 0.05 * exp_term


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", default="all", choices=["images", "kaggle", "template", "all"])
    args = ap.parse_args()

    rows = []
    for path in sorted(GOLD.glob("*.json")):
        if path.name == "kaggle_sample.json":
            continue
        gold = json.loads(path.read_text(encoding="utf-8"))
        if not gold.get("labeller") or not (GOLD / f"{path.stem}.txt").exists():
            continue
        if args.group != "all" and group_of(path.stem) != args.group:
            continue
        text = (GOLD / f"{path.stem}.txt").read_text(encoding="utf-8")
        rx = extract_metadata(text)
        nr = ner_parser.parse_resume(text, rx)
        rows.append({
            "gold": (sorted(canonical(gold.get("skills", []))), gold.get("experience_years")),
            "regex": ([s for s in rx["skills"] if s != "N/A"], rx["experience"]),
            "ner": ([s for s in nr["skills"] if s != "N/A"], nr["experience"]),
        })
    if len(rows) < 3:
        sys.exit("need at least 3 labelled resumes in this group")

    # Experience term: score only the resumes that have a gold experience figure
    # (the rest have none to compare against). Fall back to skills only if too few.
    with_exp = [r for r in rows if r["gold"][1] is not None]
    use_exp = len(with_exp) >= 3
    if use_exp:
        rows = with_exp
    jds = [(j["jd_id"], j["text"]) for j in JOB_PROFILES] + [(j["jd_id"], j["text"]) for j in EXTRA_JDS]
    report = {"group": args.group, "resumes": len(rows), "jds": {}}
    summary = {"regex": [], "ner": []}
    for jd_id, jd in jds:
        ideal = [structured(r["gold"][0], r["gold"][1] if use_exp else None, jd) for r in rows]
        entry = {}
        for m in ("regex", "ner"):
            got = [structured(r[m][0], r[m][1] if use_exp else None, jd) for r in rows]
            mae = float(np.mean(np.abs(np.array(got) - np.array(ideal))))
            rho = spearman(got, ideal)
            entry[m] = {"mae_points_of_15": round(mae, 3), "spearman_vs_gold": None if rho is None else round(rho, 3)}
            summary[m].append((mae, rho))
        report["jds"][jd_id] = entry
    report["mean"] = {m: {
        "mae_points_of_15": round(float(np.mean([a for a, _ in v])), 3),
        "spearman_vs_gold": (round(float(np.mean([b for _, b in v if b is not None])), 3)
                             if any(b is not None for _, b in v) else None),
        "jds_with_defined_ordering": sum(b is not None for _, b in v)} for m, v in summary.items()}

    out = BACKEND / "training" / "results" / f"ranking_impact_{args.group}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"group={args.group} resumes={len(rows)}  (error is in points out of the 15 the parser controls)")
    print(f"{'JD':18}{'regex err':>11}{'ner err':>9}{'regex rho':>11}{'ner rho':>9}")
    for jd_id, e in report["jds"].items():
        print(f"{jd_id:18}{e['regex']['mae_points_of_15']:>11}{e['ner']['mae_points_of_15']:>9}"
              f"{str(e['regex']['spearman_vs_gold']):>11}{str(e['ner']['spearman_vs_gold']):>9}")
    m = report["mean"]
    print(f"{'MEAN':18}{m['regex']['mae_points_of_15']:>11}{m['ner']['mae_points_of_15']:>9}"
          f"{str(m['regex']['spearman_vs_gold']):>11}{str(m['ner']['spearman_vs_gold']):>9}")


if __name__ == "__main__":
    main()
