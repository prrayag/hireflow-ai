"""Match free-text skills (JD phrases against a candidate's skills) with Sentence-BERT.

Used as the `match_fn` of dl_pipeline.skill_gap. It reuses the bi-encoder that
processor.py already loads, so no extra model is downloaded. If the encoder cannot
be loaded, only the cheap lexical rules are applied.

Environment:
    FREE_TEXT_SKILLS            "true" (default) or "false" to switch the feature off
    SKILL_MATCH_THRESHOLD       cosine similarity needed to call two skills the same
"""

from __future__ import annotations

import os
import re

ENABLED = os.getenv("FREE_TEXT_SKILLS", "true").lower() in {"1", "true", "yes"}
THRESHOLD = float(os.getenv("SKILL_MATCH_THRESHOLD", "0.75"))


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower().replace("colour", "color")))


def _lexical(phrase: str, pool: list[str]) -> bool:
    """Same words, or one skill's words contained in the other's ("Wound Care" / "Advanced wound care")."""
    pw = _words(phrase)
    for skill in pool:
        sw = _words(skill)
        if pw and sw and (pw <= sw or sw <= pw):
            return True
    return False


def match_skills(phrases: list[str], pool: list[str], threshold: float | None = None) -> set[str]:
    """Return the phrases that match at least one skill in `pool`."""
    threshold = THRESHOLD if threshold is None else threshold
    hits = {p for p in phrases if _lexical(p, pool)}
    rest = [p for p in phrases if p not in hits]
    if rest and pool:
        try:
            from processor import _get_bi_encoder  # imported lazily: processor imports this module's users
            encoder = _get_bi_encoder()
            a = encoder.encode(rest, normalize_embeddings=True, show_progress_bar=False)
            b = encoder.encode(list(pool), normalize_embeddings=True, show_progress_bar=False)
            best = (a @ b.T).max(axis=1)
            hits |= {p for p, score in zip(rest, best) if score >= threshold}
        except Exception as exc:
            print(f"[HireFlow] Semantic skill matching unavailable, lexical only: {exc}")
    return hits


def similarity_table(phrases: list[str], pool: list[str]):
    """Best cosine similarity per phrase (for threshold analysis)."""
    from processor import _get_bi_encoder
    encoder = _get_bi_encoder()
    a = encoder.encode(phrases, normalize_embeddings=True, show_progress_bar=False)
    b = encoder.encode(pool, normalize_embeddings=True, show_progress_bar=False)
    return (a @ b.T).max(axis=1)
