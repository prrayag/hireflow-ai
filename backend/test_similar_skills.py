"""
Tests for the DL features: skill extraction, gap analysis (similar skills) and summary.
Run: python test_similar_skills.py
"""

import os
os.environ.setdefault("HIREFLOW_USE_SPARK", "0")

from processor import create_gap_analysis, find_similar_candidate_skills, generate_resume_summary
from skill_extractor import extract_skills

# ── Skill extraction ────────────────────────────────────────────────────────────
# Exact pass: whole words only ("R&D" is not R, PostgreSQL is not SQL)
assert extract_skills("I work in R&D on PostgreSQL and algorithm design")["skills"] == ["PostgreSQL"]
assert extract_skills("Worked with Amazon Web Services daily")["skills"] == ["AWS"]  # alias

# Embedding pass: spelling variants inside a skills list
r = extract_skills("Skills: nodejs, postgres, ReactJS, Communication, Teamwork")
assert {"Node.js", "PostgreSQL", "React"} <= set(r["skills"]), r
assert len(r["dl_matches"]) == 3, r["dl_matches"]
assert not {"Communication", "Teamwork"} & set(r["skills"])  # non-skills are not mapped

# Without the DL pass the variants are missed (this is the "before")
assert extract_skills("Skills: nodejs, postgres, ReactJS", use_dl=False)["skills"] == []

# ── Gap analysis: similar skills ───────────────────────────────────────────────
similar = find_similar_candidate_skills(
    ["FastAPI", "AWS", "MySQL", "Kubernetes"], ["Flask", "Azure", "PostgreSQL", "Docker"]
)
pairs = {s["required"]: s["has"] for s in similar}
assert pairs == {"FastAPI": "Flask", "AWS": "Azure", "MySQL": "PostgreSQL", "Kubernetes": "Docker"}, pairs
assert find_similar_candidate_skills(["Figma"], ["Kubernetes", "PostgreSQL", "Linux"]) == []
assert find_similar_candidate_skills(["AWS"], ["Photoshop", "Agile"]) == []

g = create_gap_analysis(
    "Required: Python, Django, PostgreSQL, Docker, Kubernetes, AWS, React, Node.js",
    ["Python", "Django", "PostgreSQL", "Docker", "React"],
)
assert g["match_count"] == 5 and g["total_required"] == 8 and g["match_percentage"] == 62.5
assert g["missing_skills"] == ["AWS", "Kubernetes", "Node.js"]
# Docker~Kubernetes style credit can only raise the score, and never above 100%
assert g["match_percentage"] <= g["match_percentage_with_similar"] <= 100

# ── Summary ─────────────────────────────────────────────────────────────────────
resume = (
    "Machine learning engineer who built fraud detection models for a large payments company.\n"
    "Organised the annual office cricket tournament and the team lunch every month.\n"
    "Deployed PyTorch models to production and monitored them with MLflow dashboards.\n"
    "Enjoys hiking, photography and travelling to the mountains during the weekends.\n"
    "Python • PyTorch • MLflow • Docker • SQL\n"
)
summary = generate_resume_summary(resume, "Machine learning engineer with PyTorch and MLflow", max_sentences=2)
assert "PyTorch" in summary and "cricket" not in summary and "hiking" not in summary, summary
assert "•" not in summary  # skill list lines are not summary sentences

print("All DL feature tests passed")
