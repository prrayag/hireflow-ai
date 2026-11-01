"""Create a reproducible weak-label dataset from the synthetic resume archive."""

from __future__ import annotations

import argparse
import io
import json
import re
import zipfile
from collections import Counter
from pathlib import Path

import docx

from common import JOB_PROFILES, split_resume_ids, weak_label, write_jsonl


def extract_docx(data: bytes) -> str:
    document = docx.Document(io.BytesIO(data))
    return "\n".join(p.text.strip() for p in document.paragraphs if p.text.strip())


def extract_skills_section(text: str) -> list[str]:
    match = re.search(r"(?:^|\n)Skills\s*\n([^\n]+)", text, re.I)
    return [item.strip() for item in match.group(1).split(",")] if match else []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=Path("test_data/100_resumes.zip"))
    parser.add_argument("--output", type=Path, default=Path("backend/training/data"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    resumes = []
    with zipfile.ZipFile(args.archive) as archive:
        for name in sorted(archive.namelist()):
            if not name.lower().endswith(".docx"):
                continue
            text = extract_docx(archive.read(name))
            resumes.append({"resume_id": Path(name).stem, "resume_text": text,
                            "resume_skills": extract_skills_section(text)})

    splits = split_resume_ids([resume["resume_id"] for resume in resumes], args.seed)
    all_rows = []
    for resume in resumes:
        split = next(name for name, ids in splits.items() if resume["resume_id"] in ids)
        for profile in JOB_PROFILES:
            label, coverage = weak_label(resume["resume_skills"], profile["skills"])
            all_rows.append({
                **resume, "jd_id": profile["jd_id"], "jd_title": profile["title"],
                "jd_text": profile["text"], "required_skills": profile["skills"],
                "label": label, "normalized_label": label / 3.0,
                "skill_coverage": round(coverage, 4), "split": split,
                "label_source": "synthetic_skill_coverage_rule_v1",
            })

    for split in splits:
        write_jsonl(args.output / f"{split}.jsonl",
                    [row for row in all_rows if row["split"] == split])
    metadata = {
        "label_source": "weak/synthetic—not human validated",
        "seed": args.seed, "resume_count": len(resumes), "pair_count": len(all_rows),
        "splits_by_resume": {name: len(ids) for name, ids in splits.items()},
        "pairs_by_label": dict(sorted(Counter(row["label"] for row in all_rows).items())),
        "job_profiles": JOB_PROFILES,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
