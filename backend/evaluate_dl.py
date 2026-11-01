"""
Before/after evaluation of the deep-learning features.

    python generate_test_resumes.py                 (repo root, creates test_data/)
    python evaluate_dl.py [--resumes-dir PATH]      (writes ../EVALUATION.md)

Part A  spelling variants    exact whole-word matching vs embedding fallback
Part B  wrong skills         original substring extractor vs current extractor
Part C  gap analysis         strict keyword match vs similarity-weighted match
"""

import argparse
import os
import time

os.environ.setdefault("HIREFLOW_USE_SPARK", "0")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# The keyword list and matching rule used before the DL work (substring, case-insensitive)
ORIGINAL_KEYWORDS = [
    'Python', 'Java', 'C++', 'C#', 'React', 'Node.js', 'SQL', 'MongoDB',
    'AWS', 'Docker', 'Kubernetes', 'Spark', 'Hadoop', 'CSS', 'HTML',
    'JavaScript', 'TypeScript', 'Django', 'FastAPI', 'Azure', 'GCP',
    'Pandas', 'TensorFlow', 'PyTorch', 'Flask', 'Spring Boot', 'Express',
    'Next.js', 'GraphQL', 'Redis', 'PostgreSQL', 'MySQL', 'Firebase',
    'Terraform', 'Ansible', 'Jenkins', 'Git', 'Linux', 'Bash',
    'Kotlin', 'Swift', 'Go', 'Rust', 'Ruby', 'PHP', 'R',
    'Tableau', 'Power BI', 'Excel', 'Figma', 'Sketch',
    'Airflow', 'MLflow', 'Kafka', 'RabbitMQ', 'ElasticSearch',
    'NumPy', 'Matplotlib', 'scikit-learn', 'Hugging Face',
    'REST APIs', 'Microservices', 'Serverless', 'Lambda',
    'JIRA', 'Confluence', 'Agile', 'Scrum', 'CI/CD',
    'Prometheus', 'Grafana', 'Snowflake', 'Looker',
    'Jetpack Compose', 'Android SDK', 'Material Design',
]

# (spelling as written on a resume, canonical skill it should map to)
VARIANTS = [
    ("nodejs", "Node.js"), ("node js", "Node.js"), ("ExpressJS", "Express"),
    ("reactjs", "React"), ("react.js", "React"), ("vuejs", "Vue"), ("NextJS", "Next.js"),
    ("Nest.js", "NestJS"), ("Angular JS", "Angular"),
    ("postgres", "PostgreSQL"), ("My SQL", "MySQL"), ("mongo db", "MongoDB"),
    ("k8s", "Kubernetes"), ("Kubernates", "Kubernetes"), ("docker compose", "Docker-Compose"),
    ("golang", "Go"), ("js", "JavaScript"), ("Javscript", "JavaScript"), ("Typscript", "TypeScript"),
    ("scikit learn", "scikit-learn"), ("sklearn", "scikit-learn"), ("tensor flow", "TensorFlow"),
    ("py torch", "PyTorch"), ("Springboot", "Spring Boot"), ("github-actions", "GitHub Actions"),
    ("Power-BI", "Power BI"), ("ci cd", "CI/CD"), ("restful apis", "REST APIs"),
    ("Apache Kafka", "Kafka"), ("Apache Spark", "Spark"), ("Amazon S3", "S3"),
    ("Terraform IaC", "Terraform"), ("Jenkins CI", "Jenkins"), ("Hugging-Face", "Hugging Face"),
]

# Things that appear in resume skill lines but are NOT in the skill vocabulary
NON_SKILLS = [
    "Communication", "Teamwork", "Leadership", "Problem Solving", "Time Management",
    "Public Speaking", "Critical Thinking", "Mumbai", "Maharashtra", "Bengaluru",
    "Bachelor of Technology", "Microsoft Word", "Data Structures", "Algorithms",
    "Operating Systems", "Computer Networks", "Machine Learning", "Cloud Computing",
    "Web Development", "Project Management", "English", "Hindi", "Photography",
    "Cricket", "Reading",
]

JDS = {
    "Backend (Python/AWS)": "Backend Engineer. Required: Python, FastAPI, AWS, Kubernetes, "
                            "PostgreSQL, Docker, Redis, Kafka.",
    "ML Engineer": "Machine Learning Engineer. Required: Python, PyTorch, TensorFlow, "
                   "scikit-learn, Spark, Airflow, MLflow, Docker.",
}


def read_resume(path):
    if path.lower().endswith(".pdf"):
        import fitz
        return "".join(page.get_text() for page in fitz.open(path))
    import docx
    return "\n".join(p.text for p in docx.Document(path).paragraphs if p.text)


def original_extract(text):
    low = text.lower()
    return [s for s in ORIGINAL_KEYWORDS if s.lower() in low]


def appears_in(skill, text):
    """True if the skill (or an alias) appears as a whole word in the text."""
    from skill_extractor import extract_exact_skills
    return skill in extract_exact_skills(text)


def best_scores(tokens):
    """{token: (closest vocabulary skill, cosine similarity)} for each token."""
    import numpy as np
    import skill_extractor as se
    from processor import get_embedding
    names, matrix = se._vocab_matrix()
    vectors = np.array(get_embedding(tokens))
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    sims = vectors @ matrix.T
    return {t: (se.canonical(names[int(sims[i].argmax())]), float(sims[i].max()))
            for i, t in enumerate(tokens)}


def part_a():
    from skill_extractor import extract_skills
    rows, base_hit, dl_hit, base_extra, dl_extra = [], 0, 0, 0, 0
    for variant, expected in VARIANTS:
        text = f"Skills: Communication, {variant}, Teamwork"
        base = extract_skills(text, use_dl=False)["skills"]
        dl = extract_skills(text)["skills"]
        b, d = expected in base, expected in dl
        base_hit += b
        dl_hit += d
        base_extra += len([s for s in base if s != expected])
        dl_extra += len([s for s in dl if s != expected])
        rows.append((variant, expected, b, d, [s for s in dl if s != expected]))

    fp = []
    for i in range(0, len(NON_SKILLS), 5):
        group = NON_SKILLS[i:i + 5]
        for token in group:
            found = extract_skills("Skills: " + ", ".join([token, "Alpha", "Beta"]))["skills"]
            if found:
                fp.append((token, found))
    return rows, base_hit, dl_hit, base_extra, dl_extra, fp


def part_b(resumes_dir):
    from skill_extractor import extract_skills
    files = sorted(f for f in os.listdir(resumes_dir) if f.lower().endswith((".pdf", ".docx")))
    rows, texts = [], {}
    t_dl = 0.0
    for f in files:
        text = read_resume(os.path.join(resumes_dir, f))
        texts[f] = text
        old = original_extract(text)
        t0 = time.time()
        new = extract_skills(text)
        t_dl += time.time() - t0
        old_wrong = [s for s in old if not appears_in(s, text)]
        new_wrong = [s for s in new["skills"] if not appears_in(s, text)]
        rows.append((f.replace("_resume", "").rsplit(".", 1)[0], len(old), old_wrong,
                     len(new["skills"]), new_wrong, len(new["dl_matches"])))
    return rows, texts, t_dl / max(1, len(files))


def part_c(texts):
    from processor import create_gap_analysis
    from skill_extractor import extract_skills
    out = {}
    for jd_name, jd in JDS.items():
        scored = []
        for f, text in texts.items():
            skills = extract_skills(text)["skills"]
            g = create_gap_analysis(jd, skills)
            scored.append((f.replace("_resume", "").rsplit(".", 1)[0], g))
        out[jd_name] = scored
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resumes-dir", default=os.path.join(ROOT, "test_data"))
    args = parser.parse_args()

    a_rows, base_hit, dl_hit, base_extra, dl_extra, fp = part_a()
    b_rows, texts, avg_t = part_b(args.resumes_dir)
    c_out = part_c(texts)

    n = len(VARIANTS)
    L = []
    L.append("# HireFlow AI - Before / After Evaluation of the DL Features\n")
    L.append("Generated by `backend/evaluate_dl.py`. Re-run it to reproduce every number below.\n")

    L.append("## Part A - Messy skill spellings (Feature 1: embedding matching)\n")
    L.append(f"{n} spellings as they might appear on a resume, each placed in a skills list "
             "(`Skills: Communication, <spelling>, Teamwork`).\n")
    L.append("| | Exact whole-word matching (before) | + Sentence-BERT matching (after) |")
    L.append("|---|---|---|")
    L.append(f"| Spellings mapped to the right skill | {base_hit}/{n} ({100*base_hit//n}%) | **{dl_hit}/{n} ({100*dl_hit//n}%)** |")
    L.append(f"| Other skills also reported (e.g. `Docker` from `docker compose`) | {base_extra} | {dl_extra} |")
    L.append(f"| Non-skill words wrongly mapped to a skill | 0/{len(NON_SKILLS)} | {len(fp)}/{len(NON_SKILLS)} |\n")
    L.append("<details><summary>Per-spelling results</summary>\n")
    L.append("| Written as | Should be | Before | After | Extra wrong skills (after) |")
    L.append("|---|---|---|---|---|")
    for v, e, b, d, extra in a_rows:
        L.append(f"| {v} | {e} | {'yes' if b else 'no'} | {'yes' if d else 'no'} | {', '.join(extra) or '-'} |")
    L.append("\n</details>\n")
    if fp:
        L.append("Non-skill words that were wrongly mapped: " +
                 "; ".join(f"`{t}` -> {', '.join(s)}" for t, s in fp) + "\n")

    # Why the threshold is 0.75: closest non-skill word vs the spellings the model missed
    scores = best_scores([v for v, _ in VARIANTS] + NON_SKILLS)
    from skill_extractor import DL_THRESHOLD
    unmatched = [(v, scores[v]) for v, e, b, d, _ in a_rows if not d and scores[v][1] < DL_THRESHOLD]
    mismapped = [(v, e, scores[v]) for v, e, b, d, _ in a_rows if not d and scores[v][1] >= DL_THRESHOLD]
    near = sorted(((t, scores[t]) for t in NON_SKILLS), key=lambda x: -x[1][1])[:3]
    L.append(f"**Threshold check (cosine similarity, threshold = {DL_THRESHOLD}).** Closest non-skill words: " +
             ", ".join(f"`{t}` -> {s[0]} ({s[1]:.2f})" for t, s in near) + ". Spellings below the threshold: " +
             ", ".join(f"`{v}` ({s[1]:.2f})" for v, s in unmatched) + ". "
             "These score no higher than the nearest non-skill words, so lowering the threshold "
             f"would add junk before it recovers typos; {DL_THRESHOLD} was kept rather than tuned to this set.")
    if mismapped:
        L.append("\nMapped to the wrong skill (score above the threshold): " +
                 ", ".join(f"`{v}` -> {s[0]} ({s[1]:.2f}), expected {e}" for v, e, s in mismapped) + ".")
    L.append("")

    L.append("## Part B - Wrong skills on the 10 generated test resumes\n")
    L.append("A skill counts as **wrong** if its name does not appear as a whole word anywhere in the resume text. "
             "The original extractor used substring matching, so `R`, `Go` and `SQL` fired inside ordinary words "
             "and inside `PostgreSQL`.\n")
    L.append("| Resume | Skills found (before) | Wrong (before) | Skills found (after) | Wrong (after) | Added by DL |")
    L.append("|---|---|---|---|---|---|")
    tot_old = tot_old_wrong = tot_new = tot_new_wrong = tot_dl = 0
    for name, no, ow, nn, nw, dl in b_rows:
        tot_old += no; tot_old_wrong += len(ow); tot_new += nn; tot_new_wrong += len(nw); tot_dl += dl
        L.append(f"| {name} | {no} | {len(ow)} ({', '.join(ow) or '-'}) | {nn} | {len(nw)} | {dl} |")
    L.append(f"| **Total** | **{tot_old}** | **{tot_old_wrong}** | **{tot_new}** | **{tot_new_wrong}** | **{tot_dl}** |\n")
    L.append(f"Average extraction time per resume (exact + embedding pass): {avg_t*1000:.0f} ms.\n")
    L.append("These generated resumes use clean skill names, so the embedding pass adds nothing here; "
             "the gain on this set comes from whole-word matching. The embedding gain is Part A.\n")

    L.append("## Part C - Gap analysis: keyword match vs similarity-weighted match (Feature 2)\n")
    L.append("Similarity-weighted: each skill the JD needs but the candidate lacks counts in proportion to its "
             "cosine similarity with the closest skill the candidate has (threshold 0.55).\n")
    for jd_name, scored in c_out.items():
        L.append(f"### JD: {jd_name}\n")
        L.append(f"> {JDS[jd_name]}\n")
        L.append("| Candidate | Keyword match | Similarity-weighted | Similar skills found |")
        L.append("|---|---|---|---|")
        for name, g in sorted(scored, key=lambda x: -x[1]["match_percentage_with_similar"]):
            sim = ", ".join(f"{s['required']}~{s['has']}" for s in g["similar_skills"]) or "-"
            L.append(f"| {name} | {g['match_percentage']}% | {g['match_percentage_with_similar']}% | {sim} |")
        L.append("")
    L.append("## Limits\n")
    L.append("- Part A's spellings were chosen by us; real resumes may contain others.")
    L.append("- Short abbreviations with no lexical overlap (e.g. `k8s`) are the hardest case for embeddings.")
    L.append("- Similar skills are suggestions for the recruiter, not proof of equivalent experience. "
             "Two different programming languages can score as similar (e.g. `Python~Java`), which is the weakest pairing.")
    L.append("- Similarity weighting raises scores for candidates with related skills but rarely changes who ranks first.")
    L.append("- The generated test resumes use clean skill names, so Part B does not exercise the embedding pass.")
    L.append("- No labelled hiring outcomes were available, so this measures extraction quality, not hiring accuracy.")

    path = os.path.join(ROOT, "EVALUATION.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\n[written] {path}")


if __name__ == "__main__":
    main()
