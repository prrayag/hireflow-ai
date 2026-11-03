"""Fine-tune DistilBERT for skill NER (token classification) on SkillSpan.

Run from the repository root:
    backend/venv/bin/python backend/training/train_ner_transformer.py
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "training"))
os.environ.setdefault("HF_HOME", str(BACKEND_DIR / ".model_cache"))

from ner_data import entity_scores, load_split  # noqa: E402
from ner_models import LABELS, LABEL_TO_ID, encode_transformer_batch, transformer_predict  # noqa: E402

DEFAULT_OUTPUT = BACKEND_DIR / "model_artifacts" / "ner_distilbert_v1"


def pick_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model", default="distilbert-base-cased")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=5e-5)
    parser.add_argument("--warmup-ratio", type=float, default=0.1)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    from transformers import (AutoModelForTokenClassification, AutoTokenizer,
                              get_linear_schedule_with_warmup)

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = pick_device()

    train_rows = [r for r in load_split("train") if r["tokens"]]
    dev_rows = [r for r in load_split("dev") if r["tokens"]]
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    model = AutoModelForTokenClassification.from_pretrained(
        args.base_model, num_labels=len(LABELS),
        id2label=dict(enumerate(LABELS)), label2id=LABEL_TO_ID,
    ).to(device)

    steps_per_epoch = (len(train_rows) + args.batch_size - 1) // args.batch_size
    total_steps = steps_per_epoch * args.epochs
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    scheduler = get_linear_schedule_with_warmup(optimizer, int(total_steps * args.warmup_ratio),
                                                total_steps)
    print(f"Fine-tuning {args.base_model} on {device}: "
          f"{sum(p.numel() for p in model.parameters()):,} parameters, {total_steps} steps")

    history, best_f1 = [], -1.0
    started = time.time()
    for epoch in range(1, args.epochs + 1):
        model.train()
        order = list(range(len(train_rows)))
        random.shuffle(order)
        losses = []
        for start in range(0, len(order), args.batch_size):
            batch = [train_rows[i] for i in order[start:start + args.batch_size]]
            encoding, _ = encode_transformer_batch(tokenizer, [r["tokens"] for r in batch],
                                                   args.max_length, [r["labels"] for r in batch])
            # Cross-entropy over first sub-words; other positions carry label -100.
            loss = model(**{k: v.to(device) for k, v in encoding.items()}).loss
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            losses.append(loss.item())
        predicted, _ = transformer_predict(model, tokenizer, [r["tokens"] for r in dev_rows],
                                           device, max_length=args.max_length)
        dev_scores = entity_scores([r["labels"] for r in dev_rows], predicted)
        record = {"epoch": epoch, "train_loss": round(float(np.mean(losses)), 4),
                  "dev_micro_f1": dev_scores["micro"]["f1"], "dev_tech_f1": dev_scores["TECH"]["f1"],
                  "dev_soft_f1": dev_scores["SOFT"]["f1"],
                  "elapsed_seconds": round(time.time() - started, 1)}
        history.append(record)
        print(json.dumps(record), flush=True)
        if dev_scores["micro"]["f1"] > best_f1:
            best_f1 = dev_scores["micro"]["f1"]
            model.save_pretrained(args.output)
            tokenizer.save_pretrained(args.output)

    best_epoch = max(history, key=lambda r: r["dev_micro_f1"])
    (args.output / "training_metadata.json").write_text(json.dumps({
        "model": f"{args.base_model} fine-tuned for token classification",
        "dataset": "SkillSpan (Zhang et al., NAACL 2022), CC BY 4.0 - human-annotated job postings",
        "train_sentences": len(train_rows), "dev_sentences": len(dev_rows), "labels": LABELS,
        "hyperparameters": {"lr": args.lr, "batch_size": args.batch_size, "epochs": args.epochs,
                            "warmup_ratio": args.warmup_ratio, "weight_decay": 0.01,
                            "optimizer": "AdamW + linear warmup/decay", "grad_clip": 1.0,
                            "max_length": args.max_length, "seed": args.seed, "device": device},
        "best_epoch": best_epoch, "history": history,
        "training_seconds": round(time.time() - started, 1),
    }, indent=2), encoding="utf-8")
    print(f"Saved best model (dev micro F1 {best_f1:.4f}) to {args.output}")


if __name__ == "__main__":
    main()
