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
                "ner_only_skills": resume.get("ner_only_skills", []),
                "soft_skills": resume.get("soft_skills", []),
                "skill_parser": resume.get("skill_parser", "dictionary"),
            },
        })
    return records


def skill_gap(resume_skills: list[str], jd_text: str,
              jd_skills: list[str] | None = None) -> dict[str, object]:
    """Compare resume skills with the JD's skills.

    jd_skills lets the caller pass skills found by the NER model; by default the
    JD is matched against the dictionary only. Comparison is case-insensitive so
    NER spans such as "snowflake" match "Snowflake".
    """
    if jd_skills is None:
        jd_skills = extract_skills(jd_text)
    candidate = {skill.lower() for skill in resume_skills}
    matched = [skill for skill in jd_skills if skill.lower() in candidate]
    missing = [skill for skill in jd_skills if skill.lower() not in candidate]
    coverage = len(matched) / len(jd_skills) * 100.0 if jd_skills else 0.0
    return {"jd_skills": jd_skills, "matched_skills": matched,
            "missing_skills": missing, "skill_coverage": round(coverage, 2)}


_MONTHS = {name: index for index, name in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}
_MONTH_WORD = (r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
               r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?")
_ONGOING = r"present|current(?:ly)?|now|today|till\s+date|to\s+date|date|ongoing"


def _date_pattern(prefix: str) -> str:
    """A date such as "2019", "Jan 2019", "January, 2019", "06/2019" or "6-2019"."""
    return (rf"(?:(?P<{prefix}m>{_MONTH_WORD})\s*,?\s*|(?P<{prefix}n>\d{{1,2}})\s*[/.\-]\s*)?"
            rf"(?P<{prefix}y>(?:19|20)\d{{2}})")


_DATE_RANGE = re.compile(
    _date_pattern("s") + r"\s*(?:-|–|—|to|until|till)\s*(?:"
    + _date_pattern("e") + rf"|(?P<ongoing>{_ONGOING}))\b",
    re.I,
)


def _month_index(match: re.Match, prefix: str, default_month: int) -> int:
    year = int(match.group(f"{prefix}y"))
    month_word, month_number = match.group(f"{prefix}m"), match.group(f"{prefix}n")
    if month_word:
        month = _MONTHS[month_word.lower()[:3]]
    elif month_number and 1 <= int(month_number) <= 12:
        month = int(month_number)
    else:
        month = default_month
    return year * 12 + (month - 1)


def experience_from_date_ranges(text: str, today: tuple[int, int] | None = None) -> float:
    """Total years covered by work date ranges, ignoring the education section.

    Handles "Jan 2019 - Mar 2022", "06/2019 – Present", "2018-Present" and
    "March 2020 to date". Overlapping jobs are merged so concurrent roles are not
    double-counted. Returns 0.0 when no usable range is found.
    """
    if today is None:
        from datetime import date
        now = date.today()
        today = (now.year, now.month)
    today_index = today[0] * 12 + (today[1] - 1)
    sections = split_sections(text)
    work_text = " ".join(body for name, body in sections.items()
                         if name not in {"education", "certifications"})
    intervals = []
    for match in _DATE_RANGE.finditer(work_text):
        start = _month_index(match, "s", 1)
        if match.group("ongoing"):
            end = today_index
        else:
            # A bare end year ("2019 - 2021") counts through December of that year.
            end = _month_index(match, "e", 12)
        if start <= end <= today_index + 1 and start >= 1970 * 12:
            intervals.append((start, end + 1))
    if not intervals:
        return 0.0
    intervals.sort()
    merged = [list(intervals[0])]
    for start, end in intervals[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    months = sum(end - start for start, end in merged)
    return round(months / 12.0, 1)


def requested_experience(jd_text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", jd_text, re.I)
    return float(match.group(1)) if match else None


def experience_match(candidate_years: float, jd_text: str) -> float:
    required = requested_experience(jd_text)
    if not required or required <= 0:
        return 100.0
    return min(max(float(candidate_years), 0.0) / required, 1.0) * 100.0
