"""Plot training loss and dev F1 per epoch for both NER models.

    backend/venv/bin/python backend/training/plot_ner_training.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]
MODELS = {
    "BiLSTM-CRF (from scratch)": BACKEND_DIR / "model_artifacts" / "ner_bilstm_crf_v1",
    "DistilBERT (fine-tuned)": BACKEND_DIR / "model_artifacts" / "ner_distilbert_v1",
}
OUTPUT = BACKEND_DIR / "training" / "results" / "ner_learning_curves.png"


def main() -> None:
    fig, (loss_ax, f1_ax) = plt.subplots(1, 2, figsize=(11, 4))
    for (name, path), color in zip(MODELS.items(), ("#2563eb", "#ea580c")):
        history = json.loads((path / "training_metadata.json").read_text())["history"]
        epochs = [row["epoch"] for row in history]
        loss_ax.plot(epochs, [row["train_loss"] for row in history], marker="o", color=color, label=name)
        f1_ax.plot(epochs, [row["dev_micro_f1"] for row in history], marker="o", color=color, label=name)
    loss_ax.set(title="Training loss", xlabel="Epoch", ylabel="Loss (CRF NLL / cross-entropy)")
    loss_ax.set_yscale("log")
    f1_ax.set(title="SkillSpan dev micro F1 (exact spans)", xlabel="Epoch", ylabel="F1", ylim=(0, 0.6))
    for ax in (loss_ax, f1_ax):
        ax.grid(alpha=0.3)
        ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT, dpi=150)
    print(f"Saved {OUTPUT}")


if __name__ == "__main__":
    main()
