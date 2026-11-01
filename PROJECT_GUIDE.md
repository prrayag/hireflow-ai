# HireFlow AI - Project Guide

Read this top to bottom before a viva. Everything here describes what the code in this repository actually does.
Measured results are in [EVALUATION.md](EVALUATION.md).

---

## 1. What the project does

HR teams receive hundreds of resumes per job. HireFlow takes a job description (JD) and a batch of resumes and:

1. reads the text of each resume (PDF, DOCX, TXT, scanned images, ZIP),
2. extracts email, phone, education, experience and **skills**,
3. **ranks** candidates by how close their resume is in meaning to the JD,
4. shows, for each candidate, which required skills they **have**, which they **miss**, and which **similar** skills
   they have instead, plus a short **summary**,
5. shows analytics charts built from everything stored so far.

## 2. Architecture

```
Browser (React)  <--HTTP-->  Flask API (app.py)
                                |
        text extraction  ->  metadata + skills (skill_extractor.py)
                                |
              Spark: parallelize -> flatMap(chunk 20 words) -> cache -> collect
                                |
              Sentence-BERT embeddings (384-D) on the driver
                                |
              MongoDB: chunks + vectors  --->  $vectorSearch / local cosine
                                |
              ranking -> gap analysis -> summary  ->  dashboard
```

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Axios |
| Backend | Python, Flask |
| Big data | Apache Spark (PySpark, local mode) |
| Deep learning | Sentence-BERT `all-MiniLM-L6-v2` (PyTorch), EasyOCR |
| Storage | MongoDB (Atlas vector search, or local fallback) |
| Charts | matplotlib / seaborn, rendered server-side |

## 3. The pipeline step by step

**Text extraction.** PDF -> PyMuPDF `page.get_text()`. DOCX -> python-docx paragraphs. Images -> EasyOCR
(a neural network that reads characters from pixels). ZIPs are unpacked and each file processed.

**Fields.** Email, phone, education level and years of experience come from regular expressions
(several strategies for experience: "X years of experience", date ranges, and so on).

**Skills** (`skill_extractor.py`), two passes:
1. *Exact pass*: whole-word, case-insensitive match against the vocabulary in `skill_catalog.py`
   (about 120 skills) and its aliases (`Amazon Web Services` -> `AWS`). Whole-word matters: the old substring
   matching reported `SQL` inside `PostgreSQL` and `R` or `Go` inside ordinary words.
2. *Deep-learning pass*: tokens from list-like lines (`Skills: nodejs, postgres, ...`) that were not matched
   exactly are embedded and mapped to the nearest vocabulary skill if cosine similarity >= 0.75.

**Spark.** `sc.parallelize(resumes)` splits the batch into partitions; `flatMap` turns each resume into 20-word
chunks on all cores; `cache()` keeps the chunks in memory; `collect()` (the action) brings them to the driver.
Embeddings are computed on the driver because the PyTorch model does not pickle well to workers.

**Embedding and storage.** Each chunk becomes a 384-number vector. Chunks, vectors and the candidate's metadata
are bulk-inserted into MongoDB.

**Ranking.** The JD is embedded with the same model. MongoDB `$vectorSearch` returns the closest chunks (if an
Atlas index named `vector_index` exists); otherwise the backend computes cosine similarity itself. One result per
candidate is kept. Score = `0.70 x similarity + 0.30 x experience (capped at 20 years)`, then rescaled to the
range 55-95% for display. So the percentage is a relative ranking aid, not a probability.

**Gap analysis, summary.** Described in section 4. Computed for the top 10 candidates.

## 4. The deep-learning parts

### 4.1 Sentence embeddings (ranking)
A Transformer (MiniLM, 6 layers) turns a text into a 384-number vector so that texts with similar meaning have
vectors pointing in similar directions. **Cosine similarity** = `dot(a, b) / (|a| |b|)`; 1 means same direction,
0 unrelated. This is why "built REST services in Flask" can match a JD asking for "backend API development"
without sharing keywords.

### 4.2 Skill recognition from spelling variants
Subword tokenisation makes `nodejs`, `node js` and `Node.js` produce similar vectors (0.94-0.97). On 34 messy
spellings the exact matcher recovered 7 (20%) and the embedding pass 26 (76%), with no non-skill word wrongly
mapped (0 of 25). It does **not** fix typos or abbreviations with no overlap (`k8s`, `golang`, `Typscript`): their
similarity is no higher than that of unrelated words, so a lower threshold would add junk. See EVALUATION.md.

### 4.3 Gap analysis with similar skills
Required skills come from the JD with the same extractor. Skills the candidate lacks are compared with the skills
they have. Embedding a bare name works badly (`FastAPI` vs `Flask` = 0.23 but `Docker` vs `Photoshop` = 0.27), so
each skill is embedded with a short category description (`Python web framework: Flask`). Then related skills
score 0.58-0.77 and unrelated ones 0.23 or less, and a threshold of 0.55 separates them. Example:
`needs AWS -> has Azure (73%)`, `needs FastAPI -> has Flask (58%)`.
The **keyword match** counts exact skills only; the **similarity-weighted match** adds each similar skill in
proportion to its similarity (not as a full match). Similar skills are hints for the recruiter, not proof.

### 4.4 Extractive summary
The resume is split into sentences (skill lists, contact lines and date lines are dropped), each is embedded, and
the 3 sentences closest to the JD are returned in their original order. Nothing is generated; every word comes
from the resume.

### 4.5 EasyOCR
A CNN-based text detector plus a recurrent recogniser; used only for image resumes.

## 5. Spark in this project

| Term | Meaning | In this code |
|---|---|---|
| RDD | Immutable, partitioned, fault-tolerant collection | `sc.parallelize(resumes, n)` |
| Transformation | Lazy; builds a new RDD | `flatMap(_process_single_resume)` |
| Action | Triggers execution | `collect()` |
| DAG | Graph of the planned transformations | `parallelize -> flatMap` |
| Stage | Run of tasks with no shuffle between them | one stage (no shuffle) |
| Task | One partition on one core | one per partition |
| Job | One action | one `collect()` per upload |

Partitions = `min(max(4, resumes // 10), 32)`. `flatMap` is a *narrow* transformation, so no data moves between
workers. Spark UI is at http://localhost:4040 while a session is active; the dashboard shows the button only when
`/api/health` reports Spark running. Without Java (or with `HIREFLOW_USE_SPARK=0`) the same chunking runs as a
plain Python loop.

*Not implemented:* HDFS and MapReduce are not used. They are reasonable future scope for a very large resume lake
(HDFS stores replicated blocks; Spark can read them with data locality).

## 6. MongoDB
Each stored document is one chunk: `{resume_id, chunk_text, embedding[384], metadata{name, email, phone,
skills, experience, education}}`. A document store fits because resumes have different fields. If MongoDB is
unreachable the backend keeps chunks in memory, so a demo still works (data is lost on restart).

## 7. Limitations (be upfront about these)
- Skill vocabulary is about 120 hand-listed skills; skills outside it are not recognised.
- Analytics charts use a points formula (skills x 8 up to 40, experience x 3 up to 30, education bonus), not the AI score.
- The funnel chart's "Parsed OK" and "No Anomalies" stages equal the total; there is no anomaly detector.
- The 55-95% display score is a rescaling; it does not mean probability of a good hire.
- No labelled hiring outcomes were available, so quality is measured on skill extraction, not on hiring decisions.
- Embedding models can reflect biases in their training data; use the ranking as decision support.

## 8. Viva Q&A

**What is deep learning used for here?** Sentence-BERT embeddings for ranking, skill-spelling recognition and
similar-skill detection; EasyOCR for scanned resumes. The summary uses the same embeddings.

**Why embeddings instead of keyword matching?** Keywords miss synonyms and variants (`nodejs` vs `Node.js`,
`Flask` for `FastAPI`). Embeddings compare meaning. We kept the exact pass first because it is precise and free.

**How do you know the DL part helps?** `backend/evaluate_dl.py`: variants recognised 20% -> 76%; wrong skills on
10 test resumes 23 -> 0 (that one comes from whole-word matching, not from DL). We also report what does not work.

**Why a threshold of 0.75?** Closest non-skill word scores 0.71 (`Cloud Computing` -> GCP); the variants the model
recovered score 0.77-0.99. Typos score 0.43-0.67, below the junk, so no threshold recovers them without errors.

**Why describe skills by category before embedding?** Bare names embed poorly; adding the category separated
related from unrelated skills cleanly (see 4.3).

**Why not generate the summary with a language model?** It could invent facts about a candidate. Extractive
summaries only quote the resume.

**Transformation vs action in Spark?** Transformations are lazy and build the plan; an action such as `collect()`
runs it. Laziness lets Spark optimise the whole plan first.

**What makes a new Spark stage?** A shuffle (`groupByKey`, `reduceByKey`, `join`, `sortBy`). Our `flatMap` is
narrow, so there is one stage.

**Why compute embeddings on the driver?** PyTorch models are awkward to serialise to Spark workers; chunking is
the parallel part and embedding a batch on one machine is fast enough for this scale.

**What if MongoDB has no vector index?** The backend computes cosine similarity itself over the stored chunks.

**What would you improve next?** Fuzzy matching for typos, a labelled dataset to evaluate ranking quality, a
larger skill vocabulary, a real anomaly detector, and bias checks.

## 9. Files

| File | Purpose |
|---|---|
| `backend/app.py` | API routes, file parsing, metadata, analytics charts, CSV export |
| `backend/processor.py` | Spark pipeline, embeddings, ranking, gap analysis, summary |
| `backend/skill_catalog.py` | Vocabulary, categories, aliases |
| `backend/skill_extractor.py` | Exact + embedding skill extraction |
| `backend/generate_skills.py`, `generate_skill_context.py` | Build `skills.json`, `skill_context.json` |
| `backend/evaluate_dl.py` | Produces EVALUATION.md |
| `backend/test_*.py` | Tests |
| `frontend/src/pages/DashboardPage.jsx` | Rankings, gap analysis, summary, analytics UI |
| `generate_test_resumes.py` | 10 test resumes (PDF + DOCX) |
