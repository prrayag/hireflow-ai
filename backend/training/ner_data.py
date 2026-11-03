"""SkillSpan download/loading and entity-level metrics for the NER models.

SkillSpan: Zhang, Jensen, Sonniks and Plank, "SkillSpan: Hard and Soft Skill
Extraction from English Job Postings", NAACL 2022. Licensed CC BY 4.0.
https://huggingface.co/datasets/jjzha/skillspan
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from ner_models import bio_spans, merge_skillspan_tags  # noqa: E402

DATA_DIR = BACKEND_DIR.parent / "data_external" / "skillspan"
SKILLSPAN_URL = "https://huggingface.co/datasets/jjzha/skillspan/resolve/main/{split}.json"
SPLITS = ("train", "dev", "test")
ENTITY_TYPES = ("TECH", "SOFT")


def download_skillspan(data_dir: Path = DATA_DIR) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for split in SPLITS:
        target = data_dir / f"{split}.json"
        if not target.exists():
            print(f"Downloading SkillSpan {split} -> {target}")
            urllib.request.urlretrieve(SKILLSPAN_URL.format(split=split), target)


def load_split(split: str, data_dir: Path = DATA_DIR) -> list[dict]:
    """Load one SkillSpan split as {"tokens", "labels", "source", "doc"} rows."""
    path = data_dir / f"{split}.json"
    if not path.exists():
        download_skillspan(data_dir)
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            rows.append({
                "tokens": row["tokens"],
                "labels": merge_skillspan_tags(row["tags_skill"], row["tags_knowledge"]),
                "source": row["source"],
                "doc": f"{row['source']}-{row['idx']}",
            })
    return rows


def entity_scores(gold: list[list[str]], predicted: list[list[str]],
                  types: tuple[str, ...] = ENTITY_TYPES) -> dict[str, dict[str, float]]:
    """Exact-match entity precision/recall/F1 per type plus micro average.

    An entity counts as correct only when its type, start and end all match,
    which is the standard CoNLL evaluation.
    """
    counts = {name: {"tp": 0, "fp": 0, "fn": 0} for name in (*types, "micro")}
    for gold_labels, predicted_labels in zip(gold, predicted):
        gold_spans = set(bio_spans(gold_labels))
        predicted_spans = set(bio_spans(predicted_labels))
        for entity_type in types:
            g = {span for span in gold_spans if span[0] == entity_type}
            p = {span for span in predicted_spans if span[0] == entity_type}
            for name in (entity_type, "micro"):
                counts[name]["tp"] += len(g & p)
                counts[name]["fp"] += len(p - g)
                counts[name]["fn"] += len(g - p)
    scores = {}
    for name, c in counts.items():
        precision = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else 0.0
        recall = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        scores[name] = {"precision": round(precision, 4), "recall": round(recall, 4),
                        "f1": round(f1, 4), "support": c["tp"] + c["fn"]}
    return scores


if __name__ == "__main__":
    download_skillspan()
    for split in SPLITS:
        rows = load_split(split)
        spans = [span for row in rows for span in bio_spans(row["labels"])]
        print(split, len(rows), "sentences,", len({r["doc"] for r in rows}), "documents,",
              sum(s[0] == "TECH" for s in spans), "TECH,", sum(s[0] == "SOFT" for s in spans), "SOFT")
