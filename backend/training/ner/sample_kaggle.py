"""Pick a reproducible, category-balanced sample of the Kaggle resume dataset.

Reads the PDF for each chosen resume with PyMuPDF (the same call app.py uses),
and writes gold/kg_<ID>.txt plus a blank gold/kg_<ID>.json label template.
Also writes gold/kaggle_sample.json (the chosen IDs and categories) so the
selection can be reproduced and audited.

Usage (from backend/):
    python training/ner/sample_kaggle.py --data <folder containing Resume/ and data/> --n 40
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

from build_gold_workspace import TEMPLATE

MIN_CHARS, MAX_CHARS = 1200, 7000  # skip stubs and very long CVs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--n", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "gold")
    args = parser.parse_args()

    import fitz

    csv.field_size_limit(10**9)
    with open(args.data / "Resume" / "Resume.csv", encoding="utf-8", errors="ignore") as fh:
        rows = list(csv.DictReader(fh))

    by_category: dict[str, list[dict]] = {}
    for row in rows:
        pdf = args.data / "data" / "data" / row["Category"] / f"{row['ID']}.pdf"
        if pdf.exists() and MIN_CHARS <= len(row["Resume_str"]) <= MAX_CHARS:
            by_category.setdefault(row["Category"], []).append(row)

    rng = random.Random(args.seed)
    categories = sorted(by_category)
    chosen = [rng.choice(by_category[c]) for c in categories]  # one per category
    # Top up from the largest categories until we reach n.
    pool = [r for c in sorted(categories, key=lambda c: -len(by_category[c]))
            for r in by_category[c] if r not in chosen]
    rng.shuffle(pool)
    used = {r["Category"]: 1 for r in chosen}
    for row in pool:
        if len(chosen) >= args.n:
            break
        if used.get(row["Category"], 0) < 2:
            chosen.append(row)
            used[row["Category"]] = used.get(row["Category"], 0) + 1

    args.output.mkdir(parents=True, exist_ok=True)
    manifest = []
    for row in chosen:
        pdf = args.data / "data" / "data" / row["Category"] / f"{row['ID']}.pdf"
        text = "".join(page.get_text() for page in fitz.open(pdf))
        stem = f"kg_{row['ID']}"
        (args.output / f"{stem}.txt").write_text(text, encoding="utf-8")
        label_path = args.output / f"{stem}.json"
        if not label_path.exists():
            label_path.write_text(json.dumps(
                {**TEMPLATE, "source_file": f"{row['Category']}/{row['ID']}.pdf"}, indent=2),
                encoding="utf-8")
        manifest.append({"id": row["ID"], "category": row["Category"], "chars": len(text)})
    (args.output / "kaggle_sample.json").write_text(
        json.dumps({"seed": args.seed, "resumes": manifest}, indent=2), encoding="utf-8")
    print(f"wrote {len(manifest)} resumes across {len({m['category'] for m in manifest})} categories")


if __name__ == "__main__":
    main()
