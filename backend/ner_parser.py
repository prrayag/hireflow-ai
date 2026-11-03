"""Neural skill extraction for resumes and job descriptions.

The trained NER model (fine-tuned DistilBERT, or the from-scratch BiLSTM-CRF)
finds skill mentions from context, including skills that are not in the
dictionary in dl_pipeline.SKILL_ALIASES. Dictionary matches are always kept, so
the hybrid can only add skills. If no model is available or inference fails, the
parser falls back to the dictionary alone and the app keeps working.

Environment:
    NER_BACKEND         auto (default) | distilbert | bilstm_crf | off
    NER_MIN_CONFIDENCE  minimum mean token confidence for a span (default 0.6)
"""

from __future__ import annotations

import json
import os
import re
import threading

from dl_pipeline import SECTION_HEADINGS, SKILL_ALIASES, extract_skills

MODEL_DIR = os.path.join(os.path.dirname(__file__), "model_artifacts")
DISTILBERT_DIR = os.path.join(MODEL_DIR, "ner_distilbert_v1")
BILSTM_CRF_DIR = os.path.join(MODEL_DIR, "ner_bilstm_crf_v1")
NER_BACKEND = os.getenv("NER_BACKEND", "auto").lower()
NER_MIN_CONFIDENCE = float(os.getenv("NER_MIN_CONFIDENCE", "0.6"))
MAX_TOKENS_PER_SEGMENT = 120

_ALIAS_TO_CANONICAL = {alias: name for name, aliases in SKILL_ALIASES.items() for alias in aliases}
_ALIAS_TO_CANONICAL.update({name.lower(): name for name in SKILL_ALIASES})
# Spans the model sometimes tags that are not useful as skills in a ranking UI.
_IGNORED = {"skills", "skill", "experience", "knowledge", "technologies", "tools", "etc",
            "and", "or", "the", "with", "software", "systems", "technology"}
# Vague descriptions ("modern web technologies", "various tools") are not skills.
_VAGUE_PREFIX = {"modern", "various", "latest", "new", "emerging", "multiple", "different",
                 "several", "relevant", "related", "other", "cutting-edge", "state-of-the-art"}
_EDUCATION = re.compile(r"\b(degree|b\.?\s?tech|bachelor'?s?|master'?s?|m\.?\s?tech|b\.?\s?sc|m\.?\s?sc"
                        r"|ph\.?d|diploma|mba|b\.e\.|m\.s\.|b\.s\.|b\.a\.)(?!\w)", re.I)

_lock = threading.Lock()
_tagger = None
_tagger_loaded = False


class _DistilBertTagger:
    name = "distilbert-ner"

    def __init__(self, path: str):
        from transformers import AutoModelForTokenClassification, AutoTokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(path)
        self.model = AutoModelForTokenClassification.from_pretrained(path)
        self.model.eval()

    def predict(self, token_lists):
        from ner_models import transformer_predict
        return transformer_predict(self.model, self.tokenizer, token_lists, device="cpu")


class _BiLstmCrfTagger:
    name = "bilstm-crf-ner"

    def __init__(self, path: str):
        import torch
        from ner_models import BiLSTMCRF
        with open(os.path.join(path, "vocab.json"), encoding="utf-8") as handle:
            vocab = json.load(handle)
        self.word_to_id, self.char_to_id = vocab["word_to_id"], vocab["char_to_id"]
        self.labels = vocab["labels"]
        self.model = BiLSTMCRF(len(self.word_to_id), len(self.char_to_id), len(self.labels),
                               **vocab["hyperparameters"])
        self.model.load_state_dict(torch.load(os.path.join(path, "model.pt"), map_location="cpu"))
        self.model.eval()

    def predict(self, token_lists):
        import torch
        from ner_models import encode_bilstm_batch, repair_bio
        labels, confidences = [], []
        with torch.no_grad():
            for start in range(0, len(token_lists), 64):
                batch = token_lists[start:start + 64]
                words, chars, mask = encode_bilstm_batch(batch, self.word_to_id, self.char_to_id)
                paths, scores = self.model.predict(words, chars, mask)
                labels.extend(repair_bio([self.labels[t] for t in path]) for path in paths)
                confidences.extend(scores)
        return labels, confidences


def _has_distilbert_weights() -> bool:
    return any(os.path.exists(os.path.join(DISTILBERT_DIR, name))
               for name in ("model.safetensors", "pytorch_model.bin"))


def get_tagger():
    """Load the configured NER model once; None means dictionary-only mode."""
    global _tagger, _tagger_loaded
    with _lock:
        if _tagger_loaded:
            return _tagger
        _tagger_loaded = True
        candidates = []
        if NER_BACKEND in {"auto", "distilbert"} and _has_distilbert_weights():
            candidates.append((_DistilBertTagger, DISTILBERT_DIR))
        if NER_BACKEND in {"auto", "bilstm_crf"} and os.path.exists(os.path.join(BILSTM_CRF_DIR, "model.pt")):
            candidates.append((_BiLstmCrfTagger, BILSTM_CRF_DIR))
        for tagger_class, path in candidates:
            try:
                _tagger = tagger_class(path)
                print(f"[HireFlow] NER skill extractor loaded: {_tagger.name}")
                return _tagger
            except Exception as exc:
                print(f"[HireFlow] Could not load {tagger_class.name} from {path}: {exc}")
        if NER_BACKEND != "off":
            print("[HireFlow] No NER model available; skill extraction uses the dictionary only.")
        return None


def _segments(text: str) -> list[tuple[str, list[tuple[str, int, int]]]]:
    """Split text into (section, tokens) segments, one or more per line."""
    from ner_models import tokenize
    segments = []
    offset = 0
    section = "other"
    for line in text.replace("\r", "\n").split("\n"):
        heading = re.sub(r"\s+", " ", line).strip().rstrip(":").strip()
        section = next((name for name, pattern in SECTION_HEADINGS.items()
                        if pattern.fullmatch(heading)), section)
        tokens = [(tok, start + offset, end + offset) for tok, start, end in tokenize(line)]
        for start in range(0, len(tokens), MAX_TOKENS_PER_SEGMENT):
            if tokens[start:start + MAX_TOKENS_PER_SEGMENT]:
                segments.append((section, tokens[start:start + MAX_TOKENS_PER_SEGMENT]))
        offset += len(line) + 1
    return segments


def extract_entities(text: str, tagger=None) -> list[dict]:
    """Run the NER model and return de-duplicated {"text", "type", "confidence", "section"} spans."""
    from ner_models import bio_spans
    tagger = tagger or get_tagger()
    if tagger is None or not text.strip():
        return []
    segments = _segments(text)
    labels, confidences = tagger.predict([[tok for tok, _, _ in seg] for _, seg in segments])
    best: dict[tuple[str, str], dict] = {}
    for (section, segment), seg_labels, seg_conf in zip(segments, labels, confidences):
        for entity_type, start, end in bio_spans(seg_labels):
            surface = _clean(text[segment[start][1]:segment[end - 1][2]])
            confidence = sum(seg_conf[start:end]) / (end - start)
            key = (entity_type, surface.lower())
            if surface and (key not in best or confidence > best[key]["confidence"]):
                best[key] = {"text": surface, "type": entity_type,
                             "confidence": round(confidence, 4), "section": section}
    return list(best.values())


def _clean(surface: str) -> str:
    # Keep a leading "." so ".NET" survives; only trailing dots are punctuation.
    return re.sub(r"\s+", " ", surface).strip(" ,;:()[]").rstrip(".")


def canonical_skill(surface: str) -> str:
    """Map a span to the dictionary's canonical name when one exists."""
    cleaned = _clean(surface)
    if cleaned.lower() in _ALIAS_TO_CANONICAL:
        return _ALIAS_TO_CANONICAL[cleaned.lower()]
    matches = extract_skills(cleaned)
    if len(matches) == 1 and len(cleaned.split()) <= 2:
        return matches[0]
    return cleaned


def _usable_tech_span(entity: dict) -> bool:
    text = entity["text"]
    lowered = text.lower()
    # Degrees and fields of study in the education section are handled by the
    # education parser, not reported as skills.
    return (entity["type"] == "TECH" and entity["confidence"] >= NER_MIN_CONFIDENCE
            and entity.get("section") != "education"
            and (len(text) >= 2 or lowered in _ALIAS_TO_CANONICAL)
            and len(text.split()) <= 4 and not text.isdigit()
            and lowered not in _IGNORED and lowered.split()[0] not in _VAGUE_PREFIX
            and not _EDUCATION.search(text))


def _dedupe(skills: list[str]) -> list[str]:
    seen, result = set(), []
    for skill in skills:
        key = skill.lower()
        if key not in seen:
            seen.add(key)
            result.append(skill)
    return result


def parse_skills(text: str, dictionary_skills: list[str] | None = None) -> dict:
    """Hybrid skill extraction: dictionary matches plus NER spans.

    Returns skills (merged, dictionary first), ner_skills (what the model found),
    ner_only_skills (model finds the dictionary missed), soft_skills and the
    skill_parser used.
    """
    dictionary_skills = list(dictionary_skills if dictionary_skills is not None else extract_skills(text))
    result = {"skills": dictionary_skills, "ner_skills": [], "ner_only_skills": [],
              "soft_skills": [], "skill_parser": "dictionary"}
    tagger = get_tagger()
    if tagger is None:
        return result
    try:
        entities = extract_entities(text, tagger)
    except Exception as exc:
        print(f"[HireFlow] NER inference failed, using dictionary skills: {exc}")
        return result
    ner_skills = _dedupe([canonical_skill(e["text"]) for e in entities if _usable_tech_span(e)])
    known = {skill.lower() for skill in dictionary_skills}
    ner_only = [skill for skill in ner_skills if skill.lower() not in known]
    soft = _dedupe([e["text"] for e in sorted(entities, key=lambda e: -e["confidence"])
                    if e["type"] == "SOFT" and e["confidence"] >= NER_MIN_CONFIDENCE
                    and 2 <= len(e["text"].split()) <= 6])
    return {"skills": dictionary_skills + ner_only, "ner_skills": ner_skills,
            "ner_only_skills": ner_only, "soft_skills": soft[:10],
            "skill_parser": f"{tagger.name}+dictionary"}


def jd_skills(jd_text: str) -> list[str]:
    """Skills required by a job description (dictionary + NER)."""
    return parse_skills(jd_text)["skills"]
