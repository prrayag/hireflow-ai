"""Deterministic text preparation helpers for the neural ranking pipeline."""

from __future__ import annotations

import re
from collections import OrderedDict


SKILL_ALIASES = OrderedDict({
    "Python": ("python", "py"), "Java": ("java",), "C++": ("c++", "cpp"),
    "C#": ("c#", "c sharp"), "JavaScript": ("javascript", "js"),
    "TypeScript": ("typescript", "ts"), "React": ("react", "reactjs", "react.js"),
    "Node.js": ("node.js", "nodejs", "node js"), "SQL": ("sql",),
    "MongoDB": ("mongodb", "mongo db"), "PostgreSQL": ("postgresql", "postgres"),
    "MySQL": ("mysql",), "AWS": ("aws", "amazon web services"), "Azure": ("azure",),
    "GCP": ("gcp", "google cloud platform"), "Docker": ("docker", "containers"),
    "Kubernetes": ("kubernetes", "k8s"), "Spark": ("apache spark", "pyspark", "spark"),
    "Hadoop": ("hadoop",), "TensorFlow": ("tensorflow",), "PyTorch": ("pytorch", "torch"),
    "scikit-learn": ("scikit-learn", "sklearn"), "Pandas": ("pandas",),
    "NumPy": ("numpy",), "Flask": ("flask",), "Django": ("django",),
    "FastAPI": ("fastapi", "fast api"), "Spring Boot": ("spring boot",),
    "GraphQL": ("graphql",), "Redis": ("redis",), "Kafka": ("kafka", "apache kafka"),
    "Airflow": ("airflow", "apache airflow"), "Terraform": ("terraform",),
    "Ansible": ("ansible",), "Jenkins": ("jenkins",), "Git": ("git", "github", "gitlab"),
    "Linux": ("linux",), "REST APIs": ("rest api", "restful api", "web services"),
    "Microservices": ("microservices", "micro-services"),
    "CI/CD": ("ci/cd", "continuous integration", "continuous delivery"),
    "Machine Learning": ("machine learning", "ml"),
    "Deep Learning": ("deep learning", "neural network"),
    "NLP": ("nlp", "natural language processing"), "Computer Vision": ("computer vision",),
    "Figma": ("figma",), "Tableau": ("tableau",), "Power BI": ("power bi", "powerbi"),
    "Excel": ("excel",), "Agile": ("agile",), "Scrum": ("scrum",), "JIRA": ("jira",),
})

SECTION_HEADINGS = {
    "summary": re.compile(r"^(summary|profile|objective|about me)$", re.I),
    "experience": re.compile(r"^(work |professional |employment )?(experience|history)$", re.I),
    "skills": re.compile(r"^(technical |core )?(skills|competencies|technologies)$", re.I),
    "projects": re.compile(r"^(projects?|portfolio)$", re.I),
    "education": re.compile(r"^(education|academic qualifications?)$", re.I),
    "certifications": re.compile(r"^(certifications?|licenses?|courses?)$", re.I),
}


def _contains_alias(text: str, alias: str) -> bool:
    return re.search(rf"(?<![\w]){re.escape(alias)}(?![\w])", text, re.I) is not None


def extract_skills(text: str) -> list[str]:
    return [name for name, aliases in SKILL_ALIASES.items()
            if any(_contains_alias(text, alias) for alias in aliases)]


def split_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {"other": []}
    current = "other"
    for raw_line in text.replace("\r", "\n").splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        heading = line.rstrip(":").strip()
        matched = next((name for name, pattern in SECTION_HEADINGS.items()
                        if pattern.fullmatch(heading)), None)
        if matched:
            current = matched
            sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(line)
    return {name: " ".join(lines) for name, lines in sections.items() if lines}


def sentence_chunks(text: str, max_words: int = 90) -> list[dict[str, str]]:
    chunks: list[dict[str, str]] = []
    for section, section_text in split_sections(text).items():
        sentences = re.split(r"(?<=[.!?])\s+|\s*[•●▪]\s*", section_text)
        current: list[str] = []
        word_count = 0
        for sentence in (s.strip() for s in sentences if s.strip()):
            words = sentence.split()
            if current and word_count + len(words) > max_words:
                chunks.append({"section": section, "text": " ".join(current)})
                current, word_count = [], 0
            while len(words) > max_words:
                if current:
                    chunks.append({"section": section, "text": " ".join(current)})
                    current, word_count = [], 0
                chunks.append({"section": section, "text": " ".join(words[:max_words])})
                words = words[max_words:]
            if words:
                current.append(" ".join(words))
                word_count += len(words)
        if current:
            chunks.append({"section": section, "text": " ".join(current)})
    return chunks


def process_resume_record(resume: dict) -> list[dict]:
    """Convert one resume into serializable records for local or Spark execution.

    This function lives in the dependency-light preprocessing module so Spark
    workers do not need to import the Flask/Mongo/model-serving module.
    """
    records = []
    for index, chunk in enumerate(sentence_chunks(resume.get("text", ""))):
        records.append({
            "resume_id": resume.get("resume_id"),
            "chunk_index": index,
            "section": chunk["section"],
            "chunk_text": chunk["text"],
            "metadata": {
                "name": resume.get("name", "Unknown"),
                "email": resume.get("email", ""),
                "phone": resume.get("phone", "Not Found"),
                "education": resume.get("education", "Not Found"),
                "skills": resume.get("skills", []),
                "experience": resume.get("experience", 0),
                "titles": resume.get("titles", []),
                "companies": resume.get("companies", []),
                "extra_skills": resume.get("extra_skills", []),
                "parser_mode": resume.get("parser_mode", "regex-fallback"),
            },
        })
    return records


_PHRASE_CUE = re.compile(
    r"(?:required(?:\s+skills?)?|requirements?|requires?|skills?|proficien(?:t|cy)\s+in|knowledge\s+of|"
    r"experience\s+(?:with|in|using)|expertise\s+in|familiarity\s+with|must\s+have|including|such\s+as|"
    r"responsibilities\s+include|responsible\s+for|qualifications?)\s*:?\s*(.+)", re.I)
_PHRASE_FILLER = re.compile(
    r"^(?:(?:strong|excellent|good|solid|basic|advanced|proven|demonstrated|working|hands-on|"
    r"a|an|the|of|in|with|to|ability to|able to|knowledge of|experience (?:with|in))\s+)+", re.I)
_PHRASE_TAIL = re.compile(r"\s+(?:skills?|experience|knowledge|required|preferred|a plus)$", re.I)
_PHRASE_STOP = {"experience", "years", "year", "team", "work", "role", "position", "candidate", "company", "ability"}


def extract_jd_phrases(jd_text: str, limit: int = 15) -> list[str]:
    """Free-text requirements from a job description, for skills outside SKILL_ALIASES.

    Reads comma / 'and' lists that follow cues such as "Required:", "Skills:" or
    "Responsibilities include". Phrases already covered by SKILL_ALIASES, phrases with
    numbers (e.g. "5 years") and filler words are dropped.
    """
    phrases: list[str] = []
    for segment in re.split(r"[\n•●▪]|(?<=[.!?])\s+", jd_text):
        cue = _PHRASE_CUE.search(segment)
        if not cue:
            continue
        for part in re.split(r",|;|/|\band\b|\bor\b|\(|\)", cue.group(1).rstrip(". ")):
            phrase = _PHRASE_TAIL.sub("", _PHRASE_FILLER.sub("", part.strip(" .:-")))
            words = phrase.split()
            if (1 <= len(words) <= 4 and len(phrase) >= 3 and not re.search(r"\d", phrase)
                    and phrase.lower() not in _PHRASE_STOP and not extract_skills(phrase)):
                if phrase.lower() not in {p.lower() for p in phrases}:
                    phrases.append(phrase)
    return phrases[:limit]


def skill_gap(resume_skills: list[str], jd_text: str, jd_phrases: list[str] | None = None,
              candidate_extra: list[str] | None = None, match_fn=None) -> dict[str, object]:
    """Skill coverage of a resume against a JD.

    By default only SKILL_ALIASES skills count. If `match_fn` is given, free-text JD
    phrases (`jd_phrases`) also count: `match_fn(phrases, pool)` returns the phrases that
    are matched by something in `pool` (the candidate's skills plus `candidate_extra`).
    """
    jd_skills = extract_skills(jd_text)
    candidate = set(resume_skills)
    matched = [skill for skill in jd_skills if skill in candidate]
    missing = [skill for skill in jd_skills if skill not in candidate]
    total = len(jd_skills)
    if match_fn is not None and jd_phrases:
        pool = [s for s in resume_skills if s != "N/A"] + list(candidate_extra or [])
        hit = set(match_fn(jd_phrases, pool)) if pool else set()
        matched += [p for p in jd_phrases if p in hit]
        missing += [p for p in jd_phrases if p not in hit]
        total += len(jd_phrases)
    coverage = len(matched) / total * 100.0 if total else 0.0
    return {"jd_skills": jd_skills + [p for p in (jd_phrases or []) if match_fn is not None],
            "matched_skills": matched, "missing_skills": missing, "skill_coverage": round(coverage, 2)}


def requested_experience(jd_text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", jd_text, re.I)
    return float(match.group(1)) if match else None


def experience_match(candidate_years: float, jd_text: str) -> float:
    required = requested_experience(jd_text)
    if not required or required <= 0:
        return 100.0
    return min(max(float(candidate_years), 0.0) / required, 1.0) * 100.0
