"""Fine-tune the cross-encoder using soft relevance targets."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
import torch
from torch.optim import AdamW
from torch.utils.data import DataLoader, Dataset

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from training.common import read_jsonl


class PairDataset(Dataset):
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        return row["jd_text"], row["resume_text"], float(row["normalized_label"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, default=Path("backend/training/data/train.jsonl"))
    parser.add_argument("--validation", type=Path, default=Path("backend/training/data/validation.jsonl"))
    parser.add_argument("--base-model", default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    parser.add_argument("--output", type=Path, default=Path("backend/model_artifacts/cross_encoder_v1"))
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    from sentence_transformers import CrossEncoder
    model = CrossEncoder(args.base_model, num_labels=1, max_length=384)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.model.to(device)
    optimizer = AdamW(model.model.parameters(), lr=args.learning_rate)
    loss_fn = torch.nn.BCEWithLogitsLoss()

    def collate(batch):
        jd, resume, label = zip(*batch)
        tokens = model.tokenizer(list(jd), list(resume), padding=True, truncation=True,
                                 max_length=384, return_tensors="pt")
        return {key: value.to(device) for key, value in tokens.items()}, torch.tensor(label, device=device)

    train_loader = DataLoader(PairDataset(read_jsonl(args.train)), batch_size=args.batch_size,
                              shuffle=True, collate_fn=collate)
    validation_loader = DataLoader(PairDataset(read_jsonl(args.validation)), batch_size=args.batch_size,
                                   shuffle=False, collate_fn=collate)
    history = []
    best_loss = float("inf")
    args.output.mkdir(parents=True, exist_ok=True)
    for epoch in range(1, args.epochs + 1):
        model.model.train(); train_losses = []
        for tokens, labels in train_loader:
            optimizer.zero_grad()
            logits = model.model(**tokens).logits.reshape(-1)
            loss = loss_fn(logits, labels)
            loss.backward(); torch.nn.utils.clip_grad_norm_(model.model.parameters(), 1.0)
            optimizer.step(); train_losses.append(loss.item())
        model.model.eval(); validation_losses = []
        with torch.no_grad():
            for tokens, labels in validation_loader:
                logits = model.model(**tokens).logits.reshape(-1)
                validation_losses.append(loss_fn(logits, labels).item())
        record = {"epoch": epoch, "train_loss": float(np.mean(train_losses)),
                  "validation_loss": float(np.mean(validation_losses))}
        history.append(record); print(json.dumps(record))
        if record["validation_loss"] < best_loss:
            best_loss = record["validation_loss"]
            model.save_pretrained(str(args.output))

    metadata = {"base_model": args.base_model, "training_data": str(args.train),
                "label_source": "synthetic_skill_coverage_rule_v1", "epochs": args.epochs,
                "batch_size": args.batch_size, "learning_rate": args.learning_rate,
                "seed": args.seed, "device": str(device), "history": history}
    (args.output / "training_metadata.json").write_text(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
