"""Compare skill extractors: dictionary (old parser) vs BiLSTM-CRF vs DistilBERT.

1. Entity-level precision/recall/F1 on the SkillSpan test split (human labels,
   job postings never seen in training).
2. Recall on "unseen" skills: gold TECH spans that are not in the dictionary,
   which measures whether a model generalises beyond a fixed keyword list.
3. Resume-level skill-set precision/recall/F1 on the project's 100 generated
   resumes, whose true skills are known from the generator.

Run from the repository root:
    backend/venv/bin/python backend/training/evaluate_ner.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "training"))
os.environ.setdefault("HF_HOME", str(BACKEND_DIR / ".model_cache"))

import ner_parser  # noqa: E402
from common import normalize_skill, read_jsonl  # noqa: E402
from dl_pipeline import SKILL_ALIASES, extract_skills  # noqa: E402
from ner_data import entity_scores, load_split  # noqa: E402
from ner_models import bio_spans  # noqa: E402

RESULTS_DIR = BACKEND_DIR / "training" / "results"
ALIASES = {alias for name, aliases in SKILL_ALIASES.items() for alias in aliases} | {
    name.lower() for name in SKILL_ALIASES}


def dictionary_labels(tokens: list[str]) -> list[str]:
    """Label tokens covered by a dictionary alias match as TECH (the old parser)."""
    text, offsets, position = "", [], 0
    for token in tokens:
        offsets.append((position, position + len(token)))
        text += token + " "
        position += len(token) + 1
    labels = ["O"] * len(tokens)
    for alias in sorted(ALIASES, key=len, reverse=True):
        for match in re.finditer(rf"(?<![\w]){re.escape(alias)}(?![\w])", text, re.I):
            covered = [i for i, (s, e) in enumerate(offsets) if s >= match.start() and e <= match.end()]
            if covered and all(labels[i] == "O" for i in covered):
                labels[covered[0]] = "B-TECH"
                for i in covered[1:]:
                    labels[i] = "I-TECH"
    return labels


def unseen_recall(gold: list[list[str]], predicted: list[list[str]], tokens: list[list[str]]) -> dict:
    hits = total = 0
    for gold_labels, predicted_labels, words in zip(gold, predicted, tokens):
        predicted_spans = set(bio_spans(predicted_labels))
        for span in bio_spans(gold_labels):
            surface = " ".join(words[span[1]:span[2]]).lower()
            if span[0] == "TECH" and surface not in ALIASES:
                total += 1
                hits += span in predicted_spans
    return {"recall": round(hits / total, 4) if total else 0.0, "support": total}


def set_scores(gold: list[set[str]], predicted: list[set[str]]) -> dict:
    tp = sum(len(g & p) for g, p in zip(gold, predicted))
    fp = sum(len(p - g) for g, p in zip(gold, predicted))
    fn = sum(len(g - p) for g, p in zip(gold, predicted))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def load_taggers() -> dict:
    taggers = {}
    if ner_parser._has_distilbert_weights():
        taggers["distilbert"] = ner_parser._DistilBertTagger(ner_parser.DISTILBERT_DIR)
    if (Path(ner_parser.BILSTM_CRF_DIR) / "model.pt").exists():
        taggers["bilstm_crf"] = ner_parser._BiLstmCrfTagger(ner_parser.BILSTM_CRF_DIR)
    return taggers


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=RESULTS_DIR / "ner_evaluation.json")
    args = parser.parse_args()
    taggers = load_taggers()
    if not taggers:
        raise SystemExit("No trained NER model found. Run the training scripts first.")

    # 1 + 2: SkillSpan test split (human annotations).
    test_rows = [r for r in load_split("test") if r["tokens"]]
    tokens = [r["tokens"] for r in test_rows]
    gold = [r["labels"] for r in test_rows]
    predictions = {"dictionary": [dictionary_labels(t) for t in tokens]}
    latency = {}
    for name, tagger in taggers.items():
        started = time.perf_counter()
        predictions[name], _ = tagger.predict(tokens)
        latency[name] = round((time.perf_counter() - started) / len(tokens) * 1000, 3)
    skillspan = {name: {"entity_scores": entity_scores(gold, labels),
                        "unseen_tech_recall": unseen_recall(gold, labels, tokens),
                        "ms_per_sentence": latency.get(name)}
                 for name, labels in predictions.items()}

    # 3: generated resumes with known skills (synthetic ground truth).
    resumes = {}
    for split in ("train", "validation", "test"):
        for row in read_jsonl(BACKEND_DIR / "training" / "data" / f"{split}.jsonl"):
            resumes[row["resume_id"]] = row
    gold_sets = [{normalize_skill(s) for s in r["resume_skills"]} for r in resumes.values()]
    resume_level = {"dictionary": set_scores(
        gold_sets, [{normalize_skill(s) for s in extract_skills(r["resume_text"])} for r in resumes.values()])}
    for name, tagger in taggers.items():
        ner_only, hybrid = [], []
        for row in resumes.values():
            entities = ner_parser.extract_entities(row["resume_text"], tagger)
            found = {normalize_skill(ner_parser.canonical_skill(e["text"]))
                     for e in entities if ner_parser._usable_tech_span(e)}
            dictionary = {normalize_skill(s) for s in extract_skills(row["resume_text"])}
            ner_only.append(found)
            hybrid.append(found | dictionary)
        resume_level[f"{name}_only"] = set_scores(gold_sets, ner_only)
        resume_level[f"{name}+dictionary"] = set_scores(gold_sets, hybrid)

    report = {
        "skillspan_test": {
            "description": "SkillSpan test split: human-annotated job-posting sentences, not used in training.",
            "sentences": len(test_rows), "documents": len({r["doc"] for r in test_rows}),
            "systems": skillspan,
        },
        "generated_resumes": {
            "description": ("Set-level skill extraction on the project's 100 generated resumes. Ground "
                            "truth is the generator's skill list; real skills mentioned in the text but "
                            "not on that list count as false positives. These resumes were also used for "
                            "error analysis when designing the parser's span filters (skip the education "
                            "section, keep leading dots, drop vague phrases such as 'modern web "
                            "technologies'), so this is not a blind test - the SkillSpan "
                            "test split above is."),
            "resumes": len(resumes), "systems": resume_level,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    args.output.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
    print(markdown(report))


def markdown(report: dict) -> str:
    lines = ["# Skill extraction evaluation", "",
             f"## SkillSpan test split ({report['skillspan_test']['sentences']} sentences, human labels)", "",
             "| System | TECH P | TECH R | TECH F1 | SOFT F1 | Micro F1 | Unseen-skill recall | ms/sentence |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name, values in report["skillspan_test"]["systems"].items():
        s = values["entity_scores"]
        lines.append(f"| {name} | {s['TECH']['precision']:.3f} | {s['TECH']['recall']:.3f} | "
                     f"{s['TECH']['f1']:.3f} | {s['SOFT']['f1']:.3f} | {s['micro']['f1']:.3f} | "
                     f"{values['unseen_tech_recall']['recall']:.3f} | {values['ms_per_sentence'] or '-'} |")
    lines += ["", f"## Generated resumes ({report['generated_resumes']['resumes']} resumes, synthetic ground truth)", "",
              report["generated_resumes"]["description"], "",
              "| System | Precision | Recall | F1 |", "|---|---:|---:|---:|"]
    for name, s in report["generated_resumes"]["systems"].items():
        lines.append(f"| {name} | {s['precision']:.3f} | {s['recall']:.3f} | {s['f1']:.3f} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
