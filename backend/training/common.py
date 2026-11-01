"""Shared dataset and ranking-metric utilities."""

from __future__ import annotations

import json
import math
import random
import re
from pathlib import Path


JOB_PROFILES = [
    {
        "jd_id": "backend_python",
        "title": "Senior Python Backend Engineer",
        "skills": ["Python", "Django", "Flask", "FastAPI", "PostgreSQL", "Docker"],
        "text": "Senior Python backend engineer with 5+ years of experience building REST APIs. Required skills: Python, Django or Flask, FastAPI, PostgreSQL and Docker.",
    },
    {
        "jd_id": "ml_engineer",
        "title": "Machine Learning Engineer",
        "skills": ["Python", "Machine Learning", "TensorFlow", "PyTorch", "Data Science", "AWS"],
        "text": "Machine learning engineer with Python, data science, TensorFlow or PyTorch, AWS deployment and production ML experience.",
    },
    {
        "jd_id": "frontend",
        "title": "Frontend Engineer",
        "skills": ["JavaScript", "TypeScript", "React", "Angular", "Vue.js", "HTML", "CSS"],
        "text": "Frontend engineer experienced with JavaScript, TypeScript, React, Angular or Vue.js, HTML and CSS for modern responsive applications.",
    },
    {
        "jd_id": "devops",
        "title": "DevOps Engineer",
        "skills": ["AWS", "Docker", "Kubernetes", "CI/CD", "Git", "Python"],
        "text": "DevOps engineer with AWS, Docker, Kubernetes, CI/CD automation, Git and Python infrastructure tooling.",
    },
    {
        "jd_id": "java_fullstack",
        "title": "Java Full Stack Engineer",
        "skills": ["Java", "Spring Boot", "SQL", "React", "JavaScript", "Docker"],
        "text": "Java full stack engineer with Spring Boot, SQL, React, JavaScript and Docker. Experience delivering production web services is required.",
    },
]


def normalize_skill(value: str) -> str:
    return re.sub(r"[^a-z0-9+#./]", "", value.lower())


def weak_label(resume_skills: list[str], required_skills: list[str]) -> tuple[int, float]:
    candidate = {normalize_skill(skill) for skill in resume_skills}
    required = {normalize_skill(skill) for skill in required_skills}
    coverage = len(candidate & required) / len(required) if required else 0.0
    if coverage >= 0.50:
        label = 3
    elif coverage >= 0.25:
        label = 2
    elif coverage > 0:
        label = 1
    else:
        label = 0
    return label, coverage


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def split_resume_ids(resume_ids: list[str], seed: int = 42) -> dict[str, set[str]]:
    ids = sorted(set(resume_ids))
    random.Random(seed).shuffle(ids)
    train_end = int(len(ids) * 0.70)
    val_end = int(len(ids) * 0.85)
    return {"train": set(ids[:train_end]), "validation": set(ids[train_end:val_end]),
            "test": set(ids[val_end:])}


def dcg(labels: list[int], k: int) -> float:
    return sum((2 ** rel - 1) / math.log2(index + 2)
               for index, rel in enumerate(labels[:k]))


def ranking_metrics(rows: list[dict], score_key: str) -> dict[str, float]:
    per_jd = []
    for jd_id in sorted({row["jd_id"] for row in rows}):
        group = [row for row in rows if row["jd_id"] == jd_id]
        ranked = sorted(group, key=lambda row: row[score_key], reverse=True)
        relevant = sum(row["label"] >= 2 for row in group)
        top3 = ranked[:3]
        top5 = ranked[:5]
        precision3 = sum(row["label"] >= 2 for row in top3) / max(len(top3), 1)
        recall5 = sum(row["label"] >= 2 for row in top5) / max(relevant, 1)
        actual = [row["label"] for row in ranked]
        ideal = sorted((row["label"] for row in group), reverse=True)
        ndcg5 = dcg(actual, 5) / max(dcg(ideal, 5), 1e-9)
        reciprocal_rank = next((1 / (i + 1) for i, row in enumerate(ranked)
                                if row["label"] >= 2), 0.0)
        per_jd.append((precision3, recall5, ndcg5, reciprocal_rank))
    names = ("precision_at_3", "recall_at_5", "ndcg_at_5", "mrr")
    return {name: round(sum(values[i] for values in per_jd) / len(per_jd), 4)
            for i, name in enumerate(names)}
