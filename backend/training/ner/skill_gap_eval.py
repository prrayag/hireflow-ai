"""Does free-text skill matching make skill coverage useful for non-technical resumes?

Five JDs are written for roles that exist in the 10 image gold resumes, in different
wording from the resumes. For each JD one resume is the target. We compare skill coverage
under the old rule (dictionary skills only) and the new one (free-text phrases matched
to the candidate's NER skills), at several similarity thresholds.

The JDs are the author's, and only 5 of them, so this is a sanity check and not an accuracy
measurement. Read the threshold table as a sensitivity analysis: do not pick the "best" row.

Usage (from backend/):  python training/ner/skill_gap_eval.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).parent))

import ner_parser  # noqa: E402
import skill_matcher  # noqa: E402
from dl_pipeline import extract_jd_phrases, skill_gap  # noqa: E402
from evaluate_parsers import GOLD  # noqa: E402
from regex_parser import extract_metadata  # noqa: E402

# jd id -> (JD text, target resume id, related resume ids that are neither right nor wrong)
CASES = {
    "photo_editor": ("Photo Editor. Required: Adobe Photoshop, Lightroom, colour correction, batch processing, digital asset management.", "1", []),
    "registered_nurse": ("Registered Nurse. Responsibilities include patient care, wound care, case management and surgical support. Skills: clinical communication.", "3", []),
    "project_manager": ("Project Manager. Skills: project planning, stakeholder management, budget control, agile delivery, process improvement, team leadership.", "5", []),
    "finance_clerk": ("Finance Clerk. Required: financial accounting, tax accounting, accounts payable, payroll, data entry, Microsoft Office.", "10", []),
    "digital_marketer": ("Digital Marketing Specialist. Skills: SEO, paid search, Adobe Illustrator, Adobe Photoshop, data analytics, content strategy.", "8", ["6", "1"]),
}
IMAGES = [str(i) for i in range(1, 11)]


def candidate_pool(rid: str):
    text = (GOLD / f"{rid}.txt").read_text(encoding="utf-8")
    meta = ner_parser.parse_resume(text, extract_metadata(text))
    return meta["skills"], meta["extra_skills"]


def main() -> None:
    pools = {rid: candidate_pool(rid) for rid in IMAGES}
    thresholds = [0.50, 0.60, 0.70, 0.75, 0.80, 0.90]
    rows = []
    detail = {}
    for t in [None] + thresholds:  # None = old behaviour
        top1, tgt, non, n_t, n_n = 0, [], [], 0, 0
        for jd_id, (jd, target, related) in CASES.items():
            phrases = extract_jd_phrases(jd)
            cov = {}
            for rid, (skills, extra) in pools.items():
                if t is None:
                    gap = skill_gap(skills, jd)
                else:
                    gap = skill_gap(skills, jd, jd_phrases=phrases, candidate_extra=extra,
                                    match_fn=lambda ph, pool, t=t: skill_matcher.match_skills(ph, pool, t))
                cov[rid] = gap["skill_coverage"]
                if t == 0.75:
                    detail.setdefault(jd_id, {})[rid] = gap["matched_skills"]
            best = max(cov.values())
            top1 += int(cov[target] == best and best > 0 and list(cov.values()).count(best) == 1)
            tgt.append(cov[target])
            others = [v for rid, v in cov.items() if rid != target and rid not in related]
            non += others
        rows.append({"threshold": "old (dictionary only)" if t is None else t,
                     "target_resume_ranked_first_alone": f"{top1}/{len(CASES)}",
                     "mean_coverage_target": round(float(np.mean(tgt)), 1),
                     "mean_coverage_other_resumes": round(float(np.mean(non)), 1)})

    print(f"{'threshold':24}{'target first (of 5)':>22}{'target cov %':>14}{'others cov %':>14}")
    for r in rows:
        print(f"{str(r['threshold']):24}{r['target_resume_ranked_first_alone']:>22}"
              f"{r['mean_coverage_target']:>14}{r['mean_coverage_other_resumes']:>14}")
    print("\nWhat matched at threshold 0.75 (only resumes with a match):")
    for jd_id, per in detail.items():
        print(f"  {jd_id} (target {CASES[jd_id][1]}):")
        for rid, m in per.items():
            if m:
                print(f"    resume {rid}: {m}")
    out = BACKEND / "training" / "results" / "skill_gap_eval.json"
    out.write_text(json.dumps({"rows": rows, "matches_at_0.75": detail}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
