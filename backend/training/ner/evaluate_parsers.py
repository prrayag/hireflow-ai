"""Compare the regex parser with the NER parser against the hand-made gold labels.

Only resumes whose label file has a `labeller` are scored, and only fields that are
filled in (a blank name or a null experience is skipped, not counted as a miss).

Usage (from backend/):
    python training/ner/evaluate_parsers.py [--group images|kaggle|template|all]
Writes training/results/ner_evaluation.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

import ner_parser  # noqa: E402
from dl_pipeline import extract_skills  # noqa: E402
from regex_parser import extract_metadata  # noqa: E402

GOLD = Path(__file__).parent / "gold"


def group_of(stem: str) -> str:
    if stem.startswith("kg_"):
        return "kaggle"
    return "images" if stem.isdigit() else "template"


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def prf(pred: set, gold: set) -> tuple[float, float, float]:
    tp = len(pred & gold)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(gold) if gold else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def canonical(skills: list[str]) -> set[str]:
    out = set()
    for s in skills:
        c = ner_parser.normalize_skill(s, use_embeddings=False)
        if c:
            out.add(c)
    return out


class Tally:
    """Accumulates micro-averaged precision/recall/F1 over resumes."""

    def __init__(self):
        self.tp = self.fp = self.fn = 0

    def add(self, pred: set, gold: set):
        self.tp += len(pred & gold)
        self.fp += len(pred - gold)
        self.fn += len(gold - pred)

    def result(self):
        p = self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0
        r = self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0
        return {"precision": round(p, 3), "recall": round(r, 3),
                "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0,
                "tp": self.tp, "fp": self.fp, "fn": self.fn}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", default="all", choices=["images", "kaggle", "template", "all"])
    args = ap.parse_args()

    methods = ["regex", "ner"]
    fields = ["name", "degree", "experience_within_1y", "experience_mae"]
    acc = {m: {f: [] for f in fields} for m in methods}
    sets = {m: {k: Tally() for k in ("skills_canonical", "skills_text", "titles", "companies")} for m in methods}
    modes, seconds, scored = {}, {"regex": 0.0, "ner": 0.0}, 0

    for label_path in sorted(GOLD.glob("*.json")):
        if label_path.name == "kaggle_sample.json":
            continue
        gold = json.loads(label_path.read_text(encoding="utf-8"))
        stem = label_path.stem
        if not gold.get("labeller") or not (GOLD / f"{stem}.txt").exists():
            continue
        if args.group != "all" and group_of(stem) != args.group:
            continue
        text = (GOLD / f"{stem}.txt").read_text(encoding="utf-8")
        scored += 1

        t = time.time()
        rx = extract_metadata(text)
        seconds["regex"] += time.time() - t
        t = time.time()
        nr = ner_parser.parse_resume(text, rx)
        seconds["ner"] += time.time() - t
        modes[nr["parser_mode"]] = modes.get(nr["parser_mode"], 0) + 1

        # The app used the file name as the candidate name before the NER parser.
        file_name = norm(re.sub(r"\d+", "", Path(gold.get("source_file", stem)).stem))
        preds = {"regex": {**rx, "name": file_name, "titles": [], "companies": [], "extra_skills": []},
                 "ner": nr}

        for m, p in preds.items():
            if gold.get("name"):
                acc[m]["name"].append(norm(p["name"] or "") == norm(gold["name"]))
            if gold.get("degree"):
                acc[m]["degree"].append(p["education"] == gold["degree"])
            if gold.get("experience_years") is not None:
                err = abs(int(p["experience"]) - gold["experience_years"])
                acc[m]["experience_within_1y"].append(err <= 1)
                acc[m]["experience_mae"].append(err)
            if gold.get("skills"):
                have = [s for s in p["skills"] if s != "N/A"]
                sets[m]["skills_canonical"].add(canonical(have), canonical(gold["skills"]))
                sets[m]["skills_text"].add({norm(s) for s in have + p["extra_skills"]},
                                           {norm(s) for s in gold["skills"]})
            if gold.get("job_titles"):
                sets[m]["titles"].add({norm(s) for s in p["titles"]}, {norm(s) for s in gold["job_titles"]})
            if gold.get("companies"):
                sets[m]["companies"].add({norm(s) for s in p["companies"]}, {norm(s) for s in gold["companies"]})

    def mean(xs):
        return round(sum(xs) / len(xs), 3) if xs else None

    report = {"group": args.group, "resumes_scored": scored, "ner_parser_modes": modes,
              "seconds_total": {k: round(v, 2) for k, v in seconds.items()}, "methods": {}}
    for m in methods:
        report["methods"][m] = {
            "name_accuracy": mean(acc[m]["name"]), "degree_accuracy": mean(acc[m]["degree"]),
            "experience_within_1y": mean(acc[m]["experience_within_1y"]),
            "experience_mae_years": mean(acc[m]["experience_mae"]),
            **{k: v.result() for k, v in sets[m].items()},
            "n": {f: len(v) for f, v in acc[m].items()},
        }
    out = BACKEND / "training" / "results" / "ner_evaluation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"group={args.group} resumes scored={scored} ner modes={modes}")
    rows = [("name accuracy", "name_accuracy"), ("degree accuracy", "degree_accuracy"),
            ("experience within 1y", "experience_within_1y"), ("experience MAE (years)", "experience_mae_years")]
    print(f"{'':28}{'regex':>10}{'ner':>10}")
    for label, key in rows:
        print(f"{label:28}{str(report['methods']['regex'][key]):>10}{str(report['methods']['ner'][key]):>10}")
    for key in ("skills_canonical", "skills_text", "titles", "companies"):
        for stat in ("precision", "recall", "f1"):
            print(f"{key + ' ' + stat:28}{report['methods']['regex'][key][stat]:>10}{report['methods']['ner'][key][stat]:>10}")


if __name__ == "__main__":
    main()
