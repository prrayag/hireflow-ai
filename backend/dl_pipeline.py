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


def skill_gap(resume_skills: list[str], jd_text: str) -> dict[str, object]:
    jd_skills = extract_skills(jd_text)
    candidate = set(resume_skills)
    matched = [skill for skill in jd_skills if skill in candidate]
    missing = [skill for skill in jd_skills if skill not in candidate]
    coverage = len(matched) / len(jd_skills) * 100.0 if jd_skills else 0.0
    return {"jd_skills": jd_skills, "matched_skills": matched,
            "missing_skills": missing, "skill_coverage": round(coverage, 2)}


def requested_experience(jd_text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", jd_text, re.I)
    return float(match.group(1)) if match else None


def experience_match(candidate_years: float, jd_text: str) -> float:
    required = requested_experience(jd_text)
    if not required or required <= 0:
        return 100.0
    return min(max(float(candidate_years), 0.0) / required, 1.0) * 100.0
