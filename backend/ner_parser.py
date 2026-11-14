"""Neural resume parser (token-classification NER) with a regex fallback.

parse_resume(text, fallback) returns the same fields as app.py's extract_metadata
(email, phone, skills, education, experience) plus name, titles, companies,
extra_skills, parser_mode and confidence.

The model is loaded lazily and cached. If it cannot load, raises, or finds
nothing useful, the caller's regex result is returned unchanged
(parser_mode="regex-fallback"), so the app never breaks because of this module.

Environment:
    NER_MODEL    Hugging Face model id or local path (default oksomu/resume-ner)
    PARSER_MODE  "auto" (default), "ner" (no fallback on low confidence) or "regex"
"""

from __future__ import annotations

import os
import re
import threading
from datetime import datetime

from dl_pipeline import SKILL_ALIASES, extract_skills

NER_MODEL = os.getenv("NER_MODEL", "oksomu/resume-ner")
PARSER_MODE = os.getenv("PARSER_MODE", "auto").lower()

MIN_SKILL_SCORE = 0.70
MIN_ENTITY_SCORE = 0.60
SKILL_MATCH_THRESHOLD = 0.80  # cosine similarity to map a free-text skill to a canonical one
CHUNK_CHARS = 1500            # keeps each chunk inside the model's 512-token window
TRIM = " \t\r\n,;:|-•·()[]"

_pipeline = None
_pipeline_failed = False
_lock = threading.Lock()


def _get_pipeline():
    global _pipeline, _pipeline_failed
    if _pipeline_failed:
        return None
    if _pipeline is None:
        with _lock:
            if _pipeline is None and not _pipeline_failed:
                try:
                    from transformers import pipeline
                    print(f"[HireFlow] Loading NER parser: {NER_MODEL}")
                    _pipeline = pipeline("token-classification", model=NER_MODEL,
                                         aggregation_strategy="simple", device=-1)
                except Exception as exc:
                    _pipeline_failed = True
                    print(f"[HireFlow] NER parser unavailable; using regex parser: {exc}")
    return _pipeline


# ---------------------------------------------------------------- entity extraction

def _chunks(text: str) -> list[tuple[int, str]]:
    """Split on line boundaries into pieces of about CHUNK_CHARS, keeping offsets."""
    pieces, start, pos = [], 0, 0
    for line in text.splitlines(keepends=True):
        if len(line) > CHUNK_CHARS:  # one huge line: flush, then hard split on spaces
            if pos > start:
                pieces.append((start, text[start:pos]))
            at = pos
            while at < pos + len(line):
                end = min(at + CHUNK_CHARS, pos + len(line))
                cut = text.rfind(" ", at, end) if end < pos + len(line) else end
                end = cut if cut > at else end
                pieces.append((at, text[at:end]))
                at = end
            pos += len(line)
            start = pos
            continue
        if pos - start + len(line) > CHUNK_CHARS and pos > start:
            pieces.append((start, text[start:pos]))
            start = pos
        pos += len(line)
    if pos > start:
        pieces.append((start, text[start:pos]))
    return pieces


def _clean_span(text: str, start: int, end: int) -> list[tuple[str, int, int]]:
    """Grow a span to whole words (the model sometimes cuts mid-word), split it at line
    breaks (an entity never spans two lines) and trim punctuation."""
    while start > 0 and text[start - 1].isalnum():
        start -= 1
    while end < len(text) and text[end].isalnum():
        end += 1
    pieces = []
    for m in re.finditer(r"[^\n\r]+", text[start:end]):
        stripped = m.group().strip(TRIM)
        if stripped:
            s = start + m.start() + m.group().index(stripped)
            pieces.append((re.sub(r"\s+", " ", stripped), s, s + len(stripped)))
    return pieces


def run_ner(text: str) -> list[dict]:
    """Return cleaned entities with offsets into the original text."""
    ner = _get_pipeline()
    if ner is None:
        raise RuntimeError("NER model unavailable")
    entities = []
    for offset, chunk in _chunks(text):
        for ent in ner(chunk):
            for value, s, e in _clean_span(text, offset + ent["start"], offset + ent["end"]):
                entities.append({"label": ent["entity_group"], "text": value,
                                 "score": float(ent["score"]), "start": s, "end": e})
    return entities


# ---------------------------------------------------------------- field builders

_ALIAS_TO_CANON = {alias: canon for canon, aliases in SKILL_ALIASES.items() for alias in aliases}
_ALIAS_TO_CANON.update({canon.lower(): canon for canon in SKILL_ALIASES})
_encoder_cache: dict = {}


def normalize_skill(span: str, use_embeddings: bool = True) -> str | None:
    """Map a free-text skill to a canonical name from SKILL_ALIASES, or None."""
    key = span.lower().strip()
    if key in _ALIAS_TO_CANON:
        return _ALIAS_TO_CANON[key]
    found = extract_skills(span)  # e.g. "Python programming" contains the alias "python"
    if len(found) == 1:
        return found[0]
    if not use_embeddings:
        return None
    try:
        import numpy as np
        from processor import _get_bi_encoder  # reuse the already-loaded Sentence-BERT model
        encoder = _get_bi_encoder()
        if "canon" not in _encoder_cache:
            names = list(SKILL_ALIASES)
            _encoder_cache["canon"] = (names, encoder.encode(names, normalize_embeddings=True))
        names, matrix = _encoder_cache["canon"]
        sims = matrix @ encoder.encode(span, normalize_embeddings=True)
        best = int(np.argmax(sims))
        return names[best] if sims[best] >= SKILL_MATCH_THRESHOLD else None
    except Exception:
        return None


def _skills(entities: list[dict], text: str, use_embeddings: bool = True):
    # Dictionary hits are already canonical. Blank out the candidate's name first, so
    # "Debra Jenkins" is not read as the Jenkins tool (or "Java" in "Javier" style names).
    masked = text
    for e in entities:
        if e["label"] == "NAME" and e["score"] >= MIN_ENTITY_SCORE and e["start"] < 400:
            masked = masked[:e["start"]] + " " * (e["end"] - e["start"]) + masked[e["end"]:]
    canonical = list(extract_skills(masked))
    extra, seen = [], {s.lower() for s in canonical}
    for ent in entities:
        if ent["label"] != "SKILL" or ent["score"] < MIN_SKILL_SCORE:
            continue
        span = ent["text"]
        if not (2 <= len(span) <= 40) or len(span.split()) > 5:
            continue
        canon = normalize_skill(span, use_embeddings)
        if canon:
            if canon.lower() not in seen:
                canonical.append(canon)
                seen.add(canon.lower())
        elif span.lower() not in seen:
            extra.append(span)
            seen.add(span.lower())
    return canonical, extra


_DEGREE_RULES = [  # checked highest first
    ("PhD", re.compile(r"\b(ph\.?d|doctorate|doctor of)\b", re.I)),
    ("Master's Degree", re.compile(r"\b(master|m\.?tech|m\.?sc|m\.?s\.?|m\.?a\.?|mba|m\.?e\.?|pgdm|mca|postgraduate)\b", re.I)),
    ("Bachelor's Degree", re.compile(r"\b(bachelor|b\.?tech|b\.?sc|b\.?s\.?|b\.?a\.?|b\.?e\.?|bba|bca|b\.?com|b\.?des)\b", re.I)),
    ("Diploma", re.compile(r"\b(diploma|associate)\b", re.I)),
]


def _degree(entities: list[dict]) -> str | None:
    texts = [e["text"] for e in entities if e["label"] == "DEGREE" and e["score"] >= MIN_ENTITY_SCORE]
    for name, pattern in _DEGREE_RULES:
        if any(pattern.search(t.replace("’", "'")) for t in texts):
            return name
    return None


_STATED_YEARS = [
    r"(\d+\.?\d*)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp\b)",
    r"(?:experience|exp)\s+(?:of\s+)?(\d+\.?\d*)\+?\s*(?:years?|yrs?)",
    r"with\s+(?:over\s+|more than\s+)?(\d+\.?\d*)\+?\s*(?:years?|yrs?)",
]
_WORD_NUMBERS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve".split())}


def _stated_years(text: str) -> int | None:
    low = text.lower()
    low = re.sub(r"\b(" + "|".join(_WORD_NUMBERS) + r")\b(?=\+?\s*(?:years?|yrs?))",
                 lambda m: str(_WORD_NUMBERS[m.group(1)]), low)
    for pattern in _STATED_YEARS:
        m = re.search(pattern, low)
        if m:
            return int(float(m.group(1)))
    return None


def _career_span(entities: list[dict], text: str) -> int | None:
    """Latest minus earliest year over DATE spans that sit next to a job title or company."""
    good = [e for e in entities if e["score"] >= MIN_ENTITY_SCORE]
    jobs = [e for e in good if e["label"] in ("TITLE", "COMPANY")]
    schools = [e for e in good if e["label"] in ("DEGREE", "INSTITUTION")]

    def gap(ent, group):  # distance in characters to the nearest entity of the group
        return min((max(a["start"] - ent["end"], ent["start"] - a["end"], 0) for a in group), default=10**9)

    years = []
    now = datetime.now().year
    for ent in good:
        # keep a date only if it sits next to a job and is strictly closer to it than to a school
        if ent["label"] != "DATE" or gap(ent, jobs) >= 150 or gap(ent, jobs) >= gap(ent, schools):
            continue
        for y in re.findall(r"\b(19[89]\d|20\d\d)\b", ent["text"]):
            years.append(int(y))
        # "2018 - Present": the model may tag "Present" as its own date, or leave it after the span
        if re.search(r"\b(present|current|now)\b", ent["text"] + " " + text[ent["end"]:ent["end"] + 20], re.I):
            years.append(now)
    # Safety net: the model sometimes skips a job's dates entirely (it tags "2015-2018"
    # in one resume and not in an identical one), so also read "2018 - Present" and
    # "2015 - 2018" ranges, with optional month names, straight from the text.
    year = r"(?:19[89]|20[0-2])\d"
    for m in re.finditer(rf"\b({year})\s*(?:-|–|—|to)\s*(?:[A-Za-z]{{3,9}}\.?\s+)?({year}|present|current|now)\b",
                         text, re.I):
        span = {"start": m.start(), "end": m.end()}
        if gap(span, jobs) < 150 and gap(span, jobs) < gap(span, schools):
            end = now if not m.group(2).isdigit() else int(m.group(2))
            years += [int(m.group(1)), end]
    return max(years) - min(years) if len(years) >= 2 else None


def _unique(values: list[str]) -> list[str]:
    """De-duplicate ignoring case, and drop truncated fragments, meaning a span that is
    only the start of a longer one ("Facility Property" next to "Facility Property
    Manager"). Suffixes are kept: "Photo Editor" is a real title inside "Assistant Photo Editor"."""
    seen, out = set(), []
    for v in values:
        if v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    return [v for v in out if len(v) > 2 and not any(v.lower() != o.lower() and o.lower().startswith(v.lower()) for o in out)]


def _name(entities: list[dict]) -> str | None:
    # A real name never overlaps a job title or company ("HR BENEFITS/LEAVE COORDINATOR"
    # at the top of a resume with no name is a title, not a person).
    others = [e for e in entities if e["label"] in ("TITLE", "COMPANY") and e["score"] >= MIN_ENTITY_SCORE]
    names = [e for e in entities if e["label"] == "NAME" and e["score"] >= MIN_ENTITY_SCORE
             and not any(o["start"] < e["end"] and e["start"] < o["end"] for o in others)]
    early = [e for e in names if e["start"] < 400]  # a name is at the top; stray spans later are not
    return max(early, key=lambda e: e["score"])["text"].title() if early else None


# ---------------------------------------------------------------- public API

def parse_resume(text: str, fallback: dict, use_embeddings: bool = True) -> dict:
    """Parse with NER, filling gaps from `fallback` (the regex parser's dict)."""
    base = {**fallback, "name": None, "titles": [], "companies": [], "extra_skills": [],
            "parser_mode": "regex-fallback", "confidence": 0.0}
    if PARSER_MODE == "regex" or not text.strip():
        return base
    try:
        entities = run_ner(text)
    except Exception as exc:
        print(f"[HireFlow] NER parse failed, using regex: {exc}")
        return base

    useful = [e for e in entities if e["label"] in ("NAME", "SKILL", "TITLE", "COMPANY", "DEGREE")
              and e["score"] >= MIN_ENTITY_SCORE]
    confidence = sum(e["score"] for e in useful) / len(useful) if useful else 0.0
    if not useful or (PARSER_MODE == "auto" and confidence < 0.70):
        return {**base, "confidence": round(confidence, 3)}

    skills, extra = _skills(entities, text, use_embeddings)
    stated = _stated_years(text)
    span = _career_span(entities, text)
    experience = stated if stated is not None else (span if span is not None else fallback.get("experience", 0))
    return {
        **base,
        "name": _name(entities),
        # No fallback to the regex skills here: `skills` already holds the same dictionary
        # hits (found on name-blanked text), so the regex list could only add false ones.
        "skills": skills or ["N/A"],
        "extra_skills": extra,
        "education": _degree(entities) or fallback.get("education", "Not Found"),
        "experience": min(int(experience), 25),
        "titles": _unique([e["text"] for e in entities if e["label"] == "TITLE" and e["score"] >= MIN_ENTITY_SCORE]),
        "companies": _unique([e["text"] for e in entities if e["label"] == "COMPANY" and e["score"] >= MIN_ENTITY_SCORE]),
        "parser_mode": "ner",
        "confidence": round(confidence, 3),
    }
