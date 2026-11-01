# HireFlow AI

AI-powered resume ranking and analytics platform. Upload resumes, retrieve candidates with a Sentence-BERT bi-encoder, rerank them with a cross-encoder neural network, and inspect skill gaps and ranking evidence.

---

## Quick Start

### Windows (your friend's machine)

**First time only — run setup:**
```
Double-click: setup_windows.bat
```

**Every time you want to start the app:**
```
Double-click: start_windows.bat
```

That's it. It opens the app in your browser automatically.

---

### Mac (Prayag's machine)

**First time only:**
```bash
# Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

**Every time:**
```bash
# Terminal 1 — Backend
cd backend && source venv/bin/activate && python3 app.py

# Terminal 2 — Frontend
cd frontend && npm run dev
```

Then open: **http://localhost:5173**

---

## Requirements

| Tool | Version | Download |
|------|---------|----------|
| Python | 3.10+ | https://python.org |
| Node.js | 18+ (LTS) | https://nodejs.org |
| npm | comes with Node | — |

---

## Project Structure

```
HireFlowAI/
├── backend/
│   ├── processor.py            # Neural retrieval + cross-encoder reranking
│   ├── dl_pipeline.py          # Section chunking, skill gaps, structured signals
│   ├── app.py                  # API, parsing and analytics
│   └── requirements.txt        # Python dependencies
│
├── frontend/
│   └── src/
│       ├── pages/              # LandingPage, Dashboard, UploadPage, AnalyticsPage
│       ├── components/         # Navbar, CandidateTable, AnimatedBackground
│       ├── styles/             # CSS per page + global tokens
│       └── hooks/              # useTheme, useScrollReveal
│
├── setup_windows.bat           # Windows: first-time install
├── start_windows.bat           # Windows: daily start script
└── start.py                    # Mac: alternative start script
```

---

## How It Works

1. **Upload** — Drop PDF/DOCX/image resumes (single files or ZIP)
2. **Parse** — Text is extracted with PyMuPDF, python-docx, or EasyOCR
3. **Retrieve** — Sentence-BERT embeds section-aware chunks and the JD
4. **Rerank** — a cross-encoder jointly reads the JD and strongest resume evidence
5. **Explain** — the API returns semantic, reranker, skill-coverage and experience signals
6. **Store** — chunk vectors are pushed to MongoDB or retained in memory as a fallback
7. **Rank** — candidates are sorted by the transparent blended neural score

The models are downloaded into `backend/.model_cache/` on first use. Set
`ENABLE_CROSS_ENCODER=false` to run only the faster bi-encoder stage.

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/upload` | POST | Upload resumes (multipart/form-data) |
| `/results` | GET | Get latest batch (reads MongoDB first) |
| `/api/big-data-stats` | GET | Analytics data for charts (MongoDB) |
| `/json-data` | GET | Full local JSON storage dump |

---

## MongoDB

Connected to **MongoDB Atlas** — cluster `HireFlowAI`, database `hireflow_db`, collection `candidates`.

Each candidate document:
```json
{
  "name": "Vishv Patel",
  "email": "vishv@gmail.com",
  "phone": "+91 ...",
  "score": 72.9,
  "shortlisted": true,
  "tab_transformer_score": 12.9,
  "vector_similarity_score": 35.0,
  "tfidf_score": 25.0,
  "skills": ["Python", "Node.js", "AWS", ...],
  "jd_matched_skills": ["Python", "AWS"],
  "experience_years": 4,
  "education": "B.Tech CSE",
  "batch_id": "...",
  "uploaded_at": "2026-05-01T..."
}
```

---

## Notes for Windows Users

- If you get a **"Python not found"** error, reinstall Python and tick ✅ **"Add to PATH"**
- If you get a **"npm not found"** error, restart your terminal after installing Node.js
- The first time `setup_windows.bat` runs it may take 5–10 minutes (downloading ML packages)
- **easyOCR** downloads ~100MB of models on first use — that's normal
