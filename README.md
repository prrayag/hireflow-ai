# HireFlow AI

AI-powered resume screening. Upload a job description and a batch of resumes; HireFlow extracts skills, ranks
candidates by semantic similarity to the job, explains the skill gap for each candidate, and shows analytics.

Stack: **React + Vite** frontend, **Flask** backend, **Apache Spark** (PySpark) for parallel processing,
**Sentence-BERT** (`all-MiniLM-L6-v2`) embeddings, **MongoDB** for storage and vector search.

---

## Deep-learning features

| Feature | What it does | Where |
|---|---|---|
| Semantic ranking | Resume chunks and the JD are embedded (384-D) and compared by cosine similarity | `processor.py` |
| Skill recognition from spelling variants | `nodejs`, `postgres`, `ReactJS` are mapped to `Node.js`, `PostgreSQL`, `React` by embedding similarity | `skill_extractor.py` |
| Gap analysis with similar skills | For each skill the JD needs and the candidate lacks, finds the closest skill the candidate has (e.g. `FastAPI` ~ `Flask`) | `processor.py` |
| Extractive resume summary | Picks the resume sentences most relevant to the JD | `processor.py` |
| OCR | EasyOCR reads scanned resumes and images | `app.py` |

Measured results (reproducible with `backend/evaluate_dl.py`) are in [EVALUATION.md](EVALUATION.md).
How it all works, with viva Q&A, is in [PROJECT_GUIDE.md](PROJECT_GUIDE.md).

---

## Quick start

**Requirements:** Python 3.10+, Node.js 18+, Java 17 (only for Spark; the app falls back to plain Python without it).

### Windows
```
setup_windows.bat      (first time only)
start_windows.bat      (every time)
```

### Manual (any OS)
```bash
# Terminal 1 - backend (http://127.0.0.1:5001)
cd backend
python -m venv venv && venv\Scripts\activate      # source venv/bin/activate on Mac/Linux
pip install -r requirements.txt
python app.py

# Terminal 2 - frontend (http://localhost:5173)
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** (the backend root `/` has no page, only `/api/...` routes).

### Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection; falls back to in-memory storage if unreachable |
| `PORT` | `5001` | Backend port |
| `HIREFLOW_USE_SPARK` | `1` | Set `0` to skip Spark and use the Python fallback |
| `HIREFLOW_SPARK_MEMORY` | `512m` | Spark driver heap (Spark needs at least ~450m) |
| `VITE_API_URL` | `http://127.0.0.1:5001/api` | Backend URL used by the frontend |

The first request is slow because Sentence-BERT (~90 MB) and EasyOCR models are downloaded and loaded.

---

## How it works

1. **Upload** a JD plus PDF / DOCX / TXT / image files or a ZIP of them.
2. **Extract text**: PyMuPDF (PDF), python-docx (DOCX), EasyOCR (images).
3. **Extract fields**: email, phone, education and experience by regex; **skills** by `skill_extractor.py`
   (exact whole-word match, then embedding match for unrecognised spellings in skill lists).
4. **Spark**: `parallelize -> flatMap` splits each resume into 20-word chunks in parallel.
5. **Embed** every chunk with Sentence-BERT and **store** chunks + vectors in MongoDB.
6. **Rank**: the JD embedding is matched against stored chunks (MongoDB `$vectorSearch`, or local cosine
   similarity when no vector index exists). Score = 70% similarity + 30% experience, rescaled to 55-95% for display.
7. **Explain**: gap analysis (has / missing / similar skills) and an extractive summary for the top candidates.
8. **Analytics** page: charts built from MongoDB with matplotlib.

---

## API

| Endpoint | Method | Description |
|---|---|---|
| `/api/upload` | POST | `jd_text` + `resumes` files. With no files it searches previously stored resumes |
| `/api/analytics` | GET | Four chart images (base64) and summary numbers |
| `/api/stats` | GET | Totals for the landing page |
| `/api/export` | POST | Rankings as CSV |
| `/api/health` | GET | `{status, mongodb, spark}` |

---

## Project structure

```
backend/
  app.py                    Flask API, file parsing, metadata extraction
  processor.py              Spark pipeline, embeddings, ranking, gap analysis, summary
  skill_catalog.py          Skill vocabulary, categories, aliases
  skill_extractor.py        Exact + embedding skill extraction
  generate_skills.py        Builds skills.json (skill embeddings)
  generate_skill_context.py Builds skill_context.json (category-aware embeddings)
  evaluate_dl.py            Before/after evaluation -> EVALUATION.md
  test_semantic_skills.py   Tests for skill matching
  test_similar_skills.py    Tests for extraction, gap analysis, summary
frontend/src/
  pages/                    LandingPage, DashboardPage (rankings + analytics tabs)
  components/               Navbar, AnimatedBackground, CandidateTable
generate_test_resumes.py    Creates 10 test resumes in test_data/
```

## Tests and evaluation

```bash
cd backend
python test_semantic_skills.py
python test_similar_skills.py
python ../generate_test_resumes.py     # creates ../test_data/
python evaluate_dl.py                  # rewrites ../EVALUATION.md
```

If you change `skill_catalog.py`, regenerate the embeddings: `python generate_skills.py` and
`python generate_skill_context.py`.

## Known limitations

- Spelling-variant matching works for near-spellings (`nodejs`, `reactjs`) but not for typos or abbreviations
  with no overlap (`k8s`, `golang`); see EVALUATION.md.
- The analytics charts use a simple points formula (skills, experience, education), not the AI match score.
- The funnel chart's "Parsed OK" and "No Anomalies" stages equal the total; there is no anomaly detector.
- The summary is extractive (selected sentences), not generated text.
- HDFS is not used; the pipeline reads uploaded files directly.
