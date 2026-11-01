"""
Skill extraction with a deep-learning fallback.

1. Exact pass: whole-word match against the skill vocabulary (and its aliases).
2. DL pass: tokens from comma/bullet separated skill lists that were NOT matched
   exactly (e.g. "nodejs", "postgres", "ReactJS") are embedded with Sentence-BERT
   and mapped to the closest vocabulary skill when cosine similarity >= threshold.
"""

import re

import numpy as np

from skill_catalog import SKILL_VOCAB, ALIASES, canonical

DL_THRESHOLD = 0.75

_EXACT_NAMES = list(dict.fromkeys(SKILL_VOCAB + list(ALIASES)))
_KNOWN_LOWER = {name.lower() for name in _EXACT_NAMES}

# Whole-word match: "SQL" must not fire inside "PostgreSQL", nor "R"/"Go" inside words
# or "R&D". Names of 2 characters or fewer are case-sensitive.
_PATTERNS = [
    (name, re.compile(
        r'(?<![\w+#.&])' + re.escape(name) + r'(?![\w+#&])',
        0 if len(name) <= 2 else re.IGNORECASE,
    ))
    for name in _EXACT_NAMES
]

_LIST_MARKS = re.compile(r'[,;|•·●▪◦]')
_SPLIT = re.compile(r'[,;|•·●▪◦/\t()]| - | – ')

_vocab_cache = None


def extract_exact_skills(text):
    """Canonical skills found as whole words in text, in vocabulary order."""
    found = []
    for name, pattern in _PATTERNS:
        if pattern.search(text):
            skill = canonical(name)
            if skill not in found:
                found.append(skill)
    return found


def candidate_skill_tokens(text):
    """Short tokens from list-like lines (>= 2 separators), e.g. 'Skills: a, b, c'."""
    tokens = []
    for line in text.splitlines():
        if len(_LIST_MARKS.findall(line)) < 2:
            continue
        line = re.sub(r'^[^:]{0,30}:', '', line)  # drop a leading "Skills:" style label
        for part in _SPLIT.split(line):
            token = part.strip(" .:-*•")
            if not (2 <= len(token) <= 30) or len(token.split()) > 3:
                continue
            if not re.search(r'[A-Za-z]', token) or '@' in token or re.search(r'\d{3,}', token):
                continue
            if token.lower() in _KNOWN_LOWER:
                continue  # already handled by the exact pass
            tokens.append(token)
    return list(dict.fromkeys(tokens))


def _vocab_matrix():
    """(names, L2-normalised embedding matrix) of the vocabulary, cached."""
    global _vocab_cache
    if _vocab_cache is None:
        from processor import load_skill_embeddings
        embeddings = load_skill_embeddings()
        names = list(embeddings.keys())
        matrix = np.array([embeddings[n] for n in names]) if names else np.zeros((0, 1))
        if names:
            matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
        _vocab_cache = (names, matrix)
    return _vocab_cache


def match_tokens(tokens, threshold=DL_THRESHOLD):
    """Map each token to its closest vocabulary skill: [(token, skill, score), ...]."""
    names, matrix = _vocab_matrix()
    if not tokens or not names:
        return []
    from processor import get_embedding
    vectors = np.array(get_embedding(tokens))
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    sims = vectors @ matrix.T
    matches = []
    for i, token in enumerate(tokens):
        j = int(np.argmax(sims[i]))
        if sims[i, j] >= threshold:
            matches.append((token, canonical(names[j]), float(sims[i, j])))
    return matches


def extract_skills(text, use_dl=True, threshold=DL_THRESHOLD):
    """
    Returns {"skills": [canonical skills], "dl_matches": [{"found", "skill", "score"}]}.
    dl_matches lists only the skills the embedding model contributed.
    """
    skills = extract_exact_skills(text)
    dl_matches = []
    if use_dl:
        for token, skill, score in match_tokens(candidate_skill_tokens(text), threshold):
            if skill not in skills:
                skills.append(skill)
                dl_matches.append({"found": token, "skill": skill, "score": round(score, 2)})
    return {"skills": skills, "dl_matches": dl_matches}
