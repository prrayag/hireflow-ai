"""Train the from-scratch BiLSTM-CRF skill tagger on SkillSpan.

Run from the repository root:
    backend/venv/bin/python backend/training/train_ner_bilstm_crf.py
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "training"))

from ner_data import entity_scores, load_split  # noqa: E402
from ner_models import LABELS, LABEL_TO_ID, PAD, UNK, BiLSTMCRF, encode_bilstm_batch  # noqa: E402

DEFAULT_OUTPUT = BACKEND_DIR / "model_artifacts" / "ner_bilstm_crf_v1"


def build_vocabularies(rows: list[dict], min_word_freq: int = 1):
    word_counts = Counter(token.lower() for row in rows for token in row["tokens"])
    char_counts = Counter(char for row in rows for token in row["tokens"] for char in token)
    words = [PAD, UNK] + sorted(w for w, c in word_counts.items() if c >= min_word_freq)
    chars = [PAD, UNK] + sorted(char_counts)
    return {w: i for i, w in enumerate(words)}, {c: i for i, c in enumerate(chars)}


def predict_labels(model, rows, word_to_id, char_to_id, batch_size=64) -> list[list[str]]:
    model.eval()
    predictions = []
    with torch.no_grad():
        for start in range(0, len(rows), batch_size):
            batch = rows[start:start + batch_size]
            words, chars, mask = encode_bilstm_batch([r["tokens"] for r in batch],
                                                     word_to_id, char_to_id)
            paths, _ = model.predict(words, chars, mask)
            predictions.extend([[LABELS[t] for t in path] for path in paths])
    return predictions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(max(1, torch.get_num_threads()))

    train_rows = [r for r in load_split("train") if r["tokens"]]
    dev_rows = [r for r in load_split("dev") if r["tokens"]]
    word_to_id, char_to_id = build_vocabularies(train_rows)
    hyper = {"word_dim": 100, "char_dim": 30, "char_filters": 50, "hidden_dim": 128, "dropout": 0.5}
    model = BiLSTMCRF(len(word_to_id), len(char_to_id), len(LABELS), **hyper)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    print(f"Training BiLSTM-CRF: {sum(p.numel() for p in model.parameters()):,} parameters, "
          f"{len(word_to_id):,} words, {len(char_to_id)} chars")

    history, best_f1, best_state, stale = [], -1.0, None, 0
    started = time.time()
    for epoch in range(1, args.epochs + 1):
        model.train()
        order = list(range(len(train_rows)))
        random.shuffle(order)
        losses = []
        for start in range(0, len(order), args.batch_size):
            batch = [train_rows[i] for i in order[start:start + args.batch_size]]
            words, chars, mask = encode_bilstm_batch([r["tokens"] for r in batch], word_to_id, char_to_id)
            tags = torch.zeros_like(words)
            for i, row in enumerate(batch):
                tags[i, :len(row["labels"])] = torch.tensor([LABEL_TO_ID[l] for l in row["labels"]])
            loss = model.loss(words, chars, tags, mask)
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            losses.append(loss.item())
        dev_scores = entity_scores([r["labels"] for r in dev_rows],
                                   predict_labels(model, dev_rows, word_to_id, char_to_id))
        record = {"epoch": epoch, "train_loss": round(float(np.mean(losses)), 4),
                  "dev_micro_f1": dev_scores["micro"]["f1"], "dev_tech_f1": dev_scores["TECH"]["f1"],
                  "dev_soft_f1": dev_scores["SOFT"]["f1"]}
        history.append(record)
        print(json.dumps(record))
        if dev_scores["micro"]["f1"] > best_f1:
            best_f1, stale = dev_scores["micro"]["f1"], 0
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            stale += 1
            if stale >= args.patience:
                print(f"Early stopping after epoch {epoch}")
                break

    args.output.mkdir(parents=True, exist_ok=True)
    torch.save(best_state, args.output / "model.pt")
    (args.output / "vocab.json").write_text(json.dumps({
        "labels": LABELS, "hyperparameters": hyper,
        "word_to_id": word_to_id, "char_to_id": char_to_id,
    }), encoding="utf-8")
    best_epoch = max(history, key=lambda r: r["dev_micro_f1"])
    (args.output / "training_metadata.json").write_text(json.dumps({
        "model": "BiLSTM-CRF (word embeddings + char CNN), trained from scratch",
        "dataset": "SkillSpan (Zhang et al., NAACL 2022), CC BY 4.0 - human-annotated job postings",
        "train_sentences": len(train_rows), "dev_sentences": len(dev_rows),
        "labels": LABELS, "hyperparameters": {**hyper, "lr": args.lr, "batch_size": args.batch_size,
                                              "optimizer": "Adam", "grad_clip": 5.0, "seed": args.seed},
        "best_epoch": best_epoch, "history": history,
        "training_seconds": round(time.time() - started, 1),
    }, indent=2), encoding="utf-8")
    print(f"Saved best model (dev micro F1 {best_f1:.4f}) to {args.output}")


if __name__ == "__main__":
    main()
