# Ranking benchmark - labelling guide

Score every resume against every job description in `labels.csv`, working
**independently** (do not discuss scores until both of you have finished).
Read the job description in `jds.json` and the resume text in `resumes/`.

| Score | Meaning |
|---|---|
| 3 | Excellent - would shortlist immediately; meets nearly all requirements |
| 2 | Good - meets the core requirements, some gaps |
| 1 | Weak - a few relevant skills, but not a real fit |
| 0 | Poor - not relevant to this role |

Rules:
- Judge the candidate, not the formatting. Ignore names, gender, age and location.
- Fill `annotator_1` (first person) and `annotator_2` (second person) with 0, 1, 2 or 3.
- Use `notes` for anything unclear. Do not look at the system's scores first.
