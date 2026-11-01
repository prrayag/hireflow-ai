# HireFlow AI - Viva Prep and Plan for the Next Evaluation

For the whole team. Read sections 1-6 tonight, then do the drill in section 8.
Everything here is checked against the code and against a live rehearsal run (numbers marked "measured").

**The one rule: only claim what you can show.** Our honest story is strong enough. Over-claiming is the
only way to lose marks, because the examiner can ask to see the code.

---

## 1. The 60-second pitch (say this first)

> HireFlow AI screens resumes against a job description. Recruiters get a ranked list, and for every candidate they
> see which required skills the candidate has, which are missing, which *similar* skills they have instead, and a
> short summary. The pipeline is Flask + React; Apache Spark chunks resumes in parallel; a pre-trained
> **Sentence-BERT transformer** converts text into 384-number vectors; MongoDB stores them and we rank by
> **cosine similarity**. We added deep learning in three places: semantic ranking, recognising skills written in
> different spellings, and finding similar skills for gap analysis. We measured the improvement on skill extraction
> and we know where it still fails.

## 2. Deep-learning inventory: what, where, result

| # | Technology | What it is | Where in the code | What it does for us |
|---|---|---|---|---|
| 1 | **Sentence-BERT `all-MiniLM-L6-v2`** | Transformer encoder, 6 layers, 384-D output, about 22M parameters. **Pre-trained, not fine-tuned by us** | `backend/processor.py` `get_embedding()` | Turns any text into a vector |
| 1a | ...used for ranking | resume chunks and the JD are embedded and compared | `process_resumes_batch`, `search_best_candidates` | Semantic ranking |
| 1b | ...used for spelling variants | unknown tokens in skill lists matched to the skill vocabulary | `backend/skill_extractor.py` `match_tokens` | `nodejs` -> Node.js |
| 1c | ...used for similar skills | category-aware skill vectors | `processor.py` `find_similar_candidate_skills`, `skill_context.json` | `needs AWS, has Azure` |
| 1d | ...used for the summary | sentences scored against the JD | `processor.py` `generate_resume_summary` | 3 most relevant sentences |
| 2 | **EasyOCR** | CRAFT text detector + CRNN recogniser | `backend/app.py` `process_file_content` | Reads scanned or image resumes |
| 3 | **Vector search** | cosine similarity; MongoDB `$vectorSearch`, or local cosine when no index | `processor.py` `search_best_candidates` | Finds closest chunks |

**Not deep learning (do not present it as such):** regex for email / phone / experience / education, Spark
chunking, the 70/30 score formula, exact whole-word skill matching, the analytics charts (points formula).

## 3. Results

### What we measured (reproduce: `cd backend && python evaluate_dl.py`, report in `EVALUATION.md`)

| Measurement | Before | After |
|---|---|---|
| 34 messy skill spellings recognised (`nodejs`, `postgres`, `ReactJS`...) | 7 (20%) | **26 (76%)** |
| Non-skill words wrongly turned into skills (25 tested) | 0 | 0 |
| Wrong skills reported on 10 test resumes | 23 | **0** |
| Skill extraction time per resume | | about 22 ms |

Be precise about the 23 -> 0: it comes from **whole-word matching**, not from deep learning. The old code matched
substrings, so `R`, `Go` and `SQL` appeared inside ordinary words and inside `PostgreSQL`. The DL gain is the
20% -> 76%.

### The demo story on one resume (measured, `demo_data/messy_resume.txt` against `demo_data/jd_backend.txt`)

| Step | Skills matched | Match |
|---|---|---|
| Keywords only | 2 of 7 | **28.6%** |
| + DL recognises `nodejs`, `postgres` | 4 of 7 | **57.1%** |
| + DL similar skills (AWS~Azure, FastAPI~Flask, Kubernetes~Docker) | weighted | **84.7%** |

### Pipeline speed (measured on the demo laptop)
10 resumes -> 88 chunks -> **about 4.5 s** ingestion (chunk + embed + store); vector search **0.02 s**.
The very first request takes about 15 s (Spark and model start-up).

### How to answer "how did performance improve?"
Three things, all about **extraction quality**: *recall* (20% -> 76% of spellings recognised), *precision* (23 -> 0
wrong skills), and *usefulness* (gap analysis, similar skills and summaries save the recruiter reading time).
**Do not say** "our hiring accuracy improved by X%". We have no recruiter-labelled data yet, so we have not measured
ranking accuracy. Say that plainly and say how you will measure it (section 10).

## 4. Live demo script (about 6 minutes)

Setup once: `python generate_test_resumes.py` in the project root creates `test_data/test_resumes_10.zip`.

| Step | Do | Expected (from rehearsal) | Say |
|---|---|---|---|
| 1 | Paste `demo_data/jd_backend.txt`, upload `test_resumes_10.zip`, click Run | 10 resumes, 88 chunks, about 4-5 s. Arjun Mehta first; Meera Nair (a designer) last | "Spark chunks in parallel, Sentence-BERT embeds, we rank by similarity" |
| 2 | Expand **Arjun Mehta** | Gap box: matched 6 of 7 (85.7%); summary | "Has / missing is explicit, the summary quotes his resume" |
| 3 | Expand **Rohan Verma** | Purple box: needs Kubernetes -> has Docker (62% similar); 57.1% -> 66.0% | "He lacks Kubernetes but has Docker; DL shows that with a similarity score" |
| 4 | Upload `demo_data/messy_resume.txt` with the same JD | Cyan box: nodejs -> Node.js, postgres -> PostgreSQL, ReactJS -> React, docker compose -> Docker-Compose. 28.6% -> 57.1% -> 84.7% | "Keywords alone found 5 skills; with the model 9. Communication and hobbies were correctly ignored" |
| 5 | Upload nothing, paste `demo_data/jd_ml.txt`, search | Priya Sharma first (clean database only) | "Searches everything stored before" |
| 6 | Analytics tab | 4 charts | "These use a points formula, not the AI score" (say it before they ask) |

If something fails: section 9, plan B.

## 5. Questions and answers

### A. Basics (everyone must answer these)
- **What is an embedding?** A list of numbers (384 here) that represents the meaning of a text. Similar meaning
  gives vectors that point in similar directions.
- **What is cosine similarity?** `dot(a,b) / (|a| x |b|)`. 1 = same direction, 0 = unrelated. It compares meaning
  and ignores text length.
- **What is a Transformer / attention?** A network where every word looks at every other word and weights how
  relevant each is, so context changes meaning ("bank" of a river vs a bank). MiniLM has 6 such layers.
- **What is transfer learning?** Reusing a model trained on a huge dataset (this one on over a billion sentence
  pairs, by the Sentence-Transformers authors) for our task without training it ourselves.
- **How does EasyOCR work?** First a network (CRAFT) finds text regions in the image, then a CNN + LSTM
  recogniser (CRNN) reads the characters in each region.
- **ML vs DL?** DL is ML with many-layer neural networks that learn their own features.

### B. Our implementation
- **Which DL technologies, and where?** The table in section 2.
- **Did you train a model?** *No.* We used a pre-trained transformer (transfer learning) and engineered the
  pipeline around it: chunking, vector search, skill vocabulary with category descriptions, thresholds chosen from
  data, and an evaluation. Fine-tuning on skill pairs is the next step (section 10).
- **Why not train your own?** No labelled hiring data and a short timeline. A pre-trained model already has strong
  general semantics; training from scratch needs millions of examples.
- **Why MiniLM?** Small (22M parameters), fast on a laptop CPU, good quality. Larger models are slower for little gain
  at our scale.
- **Why not ChatGPT or another LLM?** Resumes are personal data (privacy), API cost and latency, LLMs can
  invent facts about a candidate, and embeddings are deterministic and run offline.
- **How is a candidate ranked?** Resume split into 20-word chunks -> each embedded -> JD embedded -> cosine
  similarity -> best chunk per candidate -> `0.70 x similarity + 0.30 x experience` -> rescaled to 55-95 for display.
- **Why 20-word chunks?** So a candidate's best-matching fragment counts instead of being diluted by a long
  document. It is a design choice we did not tune; tuning it is future work.
- **How do you recognise `nodejs`?** The exact matcher fails on it, so we embed unmatched tokens from skill lists
  and take the nearest vocabulary skill if similarity is at least 0.75 (`nodejs` -> Node.js scores 0.94).
- **Why 0.75?** The closest non-skill word scored 0.71 (`Cloud Computing` -> GCP); the variants we recover score
  0.77-0.99. Typos score 0.43-0.67, no higher than junk, so no threshold fixes them safely.
- **How do similar skills work?** Bare names embed badly (`FastAPI` vs `Flask` 0.23, `Docker` vs `Photoshop` 0.27),
  so each skill is embedded with a category description ("Python web framework: Flask"). Then related skills score
  0.58-0.77 and unrelated 0.23 or less; threshold 0.55. The weighted match counts each similar skill by its score,
  not as a full match.
- **Why an extractive summary?** It only quotes the resume, so it cannot invent facts. Abstractive generation can.

### C. Results and honesty
- **What are your results?** Section 3.
- **What is the accuracy?** For skill extraction, the numbers in section 3. For ranking we do not have
  recruiter-labelled data yet; planned: label 30 resume-JD pairs and report Precision@3 and NDCG against a keyword
  baseline.
- **Why are all scores between 75 and 83?** Resumes in the same field have similar embeddings, and we rescale
  cosine similarity into 55-95 for readability. Use the score as a ranking, not an absolute percentage.
- **Why does the ranking disagree with the gap analysis?** (Example: Ananya has 0% keyword match but ranks above
  Priya.) The rank is semantic similarity plus experience; the gap is explicit skills. They are two different
  signals, shown side by side so the recruiter decides.
- **Siddharth shows 0 years.** Experience comes from regular expressions and fails on some layouts. Known limitation;
  a fix is planned.
- **Where does it fail?** `k8s`, `golang`, `Typscript`, `sklearn` (not recognised); `My SQL` becomes `SQL` instead of
  MySQL; `Python ~ Java` and `Node.js ~ React` count as similar, which is debatable. All shown in `EVALUATION.md`.

### D. System
- **Why Spark? Does it make it faster?** It chunks resumes in parallel across partitions. **At 10 resumes it gives no
  speed-up**; start-up costs seconds. It is there so the pipeline scales. The embedding step currently runs on the
  driver, which is the bottleneck; future: distribute with `mapPartitions` or use a GPU.
- **Transformation vs action?** Transformations (`flatMap`) are lazy and build a plan; an action (`collect`) runs
  it. Our job: `parallelize -> flatMap -> cache -> collect`: one job, one stage, no shuffle.
- **Is "Spark Time" on the dashboard only Spark?** No, it is the whole ingestion step: chunk + embed + store.
- **Why MongoDB?** Documents with different fields per resume, and built-in vector search on Atlas. Without an
  index we compute cosine similarity ourselves.
- **HDFS?** Not used. Reasonable future scope for a very large resume lake.
- **Privacy and bias?** Resumes are personal data; chunks are stored as plain text in MongoDB, with no retention or
  encryption policy yet. Embedding models can reflect bias in their training data, so the ranking is decision
  support. Planned: a name / gender swap test (section 10).

### E. Traps (prepare these exact answers)
- **"What is JobBERT?"** The dashboard and some docs say "JobBERT", but the model is the **general-purpose
  `all-MiniLM-L6-v2`**, not a job-specific BERT. Say: "We called it JobBERT in the UI; it is a general sentence
  model. A job-domain model is future work." Do not defend the name.
- **"Your poster mentions TabTransformer."** An earlier design, not implemented in this version. It is listed as
  future work. Do not describe it as built.
- **"Is it deployed on AWS?"** `DEPLOY_AWS.md` exists, but only say it is deployed if you actually ran it and can
  show it. Otherwise say: "Runs locally; deployment notes are prepared."
- **"Are the analytics AI?"** No: a points formula (skills x 8 up to 40, experience x 3 up to 30, education bonus).
  The funnel's "Parsed OK" and "No Anomalies" stages equal the total; there is no anomaly detector.
- **"What did *you* do?"** Section 7: each person names their area and one file.

## 6. Never say
- "Our own trained model" / "we trained" (we did not, yet).
- "98% accuracy" or any ranking accuracy (not measured).
- "Spark makes it faster" (not at this scale).
- "JobBERT" as if it were domain-trained.
- "The summary is generated by AI" (it is extractive).
- Anything about AWS or TabTransformer you cannot demonstrate.

## 7. Team roles for tomorrow

Fill in names. Each person owns one area; if asked something outside it, say "X can answer that."

| Area | Owner | Must be able to explain | Files |
|---|---|---|---|
| DL / NLP (embeddings, skills, gap, summary) | | sections 2, 3, 5B | `processor.py`, `skill_extractor.py`, `skill_catalog.py` |
| Backend, Spark, MongoDB, OCR | | Spark terms, pipeline, endpoints, fallback behaviour | `app.py`, `processor.py` (Spark part) |
| Frontend and demo | | the demo script, what each panel shows, how the frontend calls the API | `DashboardPage.jsx` |
| Evaluation, docs, QA | | `EVALUATION.md`, limitations, section 5C and 5E | `evaluate_dl.py`, `EVALUATION.md` |

Everyone must answer section 5A and the pitch.

## 8. Tonight

1. **Run the demo twice start to finish** (section 4) on the laptop you will use tomorrow.
2. **Record the demo** with a screen recorder (2-3 minutes). It is your plan B.
3. **Mock viva, 20 minutes:** one person asks, one answers, 45 seconds per answer, rotate. Use sections 5A-5E; make
   the asker pick questions from the owner's *other* areas. Re-ask any answer that took longer than 1 minute.
4. Read `EVALUATION.md` once. Know the three numbers: 20% -> 76%, 23 -> 0, 28.6% -> 57.1% -> 84.7%.
5. Sleep. A calm, honest answer beats a long confident wrong one.

## 9. Tomorrow before the examiner arrives

- [ ] Laptop plugged in; close browsers, IDEs and chat apps (Spark needs about 0.5 GB free).
- [ ] Terminal 1: `cd backend` then `python app.py`; wait for "Backend ready".
- [ ] Terminal 2: `cd frontend` then `npm run dev`; open `http://localhost:5173`.
- [ ] `http://127.0.0.1:5001/api/health` shows `"mongodb": true` and `"spark": true`.
- [ ] **Warm up:** upload `messy_resume.txt` once. The first request takes about 15 s; the rest are fast.
- [ ] **Clean test data (optional but recommended):** your database currently holds duplicates from our test runs
  (analytics showed 54 candidates). To start clean: `mongosh hireflow_db --eval "db.resumes.deleteMany({})"`.
  *This deletes everything stored*, including your own earlier uploads. Then do demo step 1 to refill it.
- [ ] Hard refresh the page (Ctrl+Shift+R). Have the recording and `EVALUATION.md` open in other tabs.

**Plan B**
- Spark fails to start: stop the backend, set `HIREFLOW_USE_SPARK=0`, start again. Say: "Spark falls back to plain Python;
  that fallback is built in."
- Page won't load: `http://localhost:5173` only; the backend root `/` has no page.
- MongoDB false: the demo still works (in-memory), but historical search and analytics start empty.
- Anything else: play the recording and walk through `EVALUATION.md`.

---

## 10. Plan for the next evaluation (about 8 days)

Assumption: viva Mon 2 Nov, evaluation about Mon 9 Nov. Adjust the dates if the evaluation is on another day.

### Goal
Turn "we used a pre-trained model" into "we measured, trained and tested", with numbers an examiner can check.
**Rule: integrate a change only if it beats the baseline on held-out data; otherwise report it as a negative
result.** A reported failure scores better than a hidden one.

### Work items, in priority order

| # | Item | Why it matters | Done when |
|---|---|---|---|
| 1 | **Ranking benchmark.** 10 resumes x 3 JDs = 30 pairs. Two people label each 0-3 independently, then reconcile. New `evaluate_ranking.py` reports Precision@3 and NDCG@5 for: keyword baseline, current score, blended score | Closes the biggest gap: "how accurate is the ranking?" | Table in `EVALUATION.md` |
| 2 | **Fix experience parsing** (Siddharth shows 0y), and make the analytics use the real score, or label the placeholder funnel stages honestly | Removes the visible weaknesses | Test resumes show sensible years; charts match the ranking |
| 3 | **Typos and abbreviations.** Add edit-distance matching (rapidfuzz) and an alias list (`k8s`, `golang`, `sklearn`, `js`) | Recovers the cases embeddings miss | Variants recognised above 90% with 0 false positives on the non-skill list, or report the real figure |
| 4 | **Fine-tune MiniLM** on skill-variant pairs (sentence-transformers, `MultipleNegativesRankingLoss`, CPU, minutes). Hold out 30% of *perturbation types* for testing | Real DL training, with train/test numbers | Held-out accuracy of fine-tuned vs pre-trained, reported either way |
| 5 | **Bias check.** Swap names and gender words in the 10 resumes, re-rank, report the average change in score | Answers the ethics question with data | One table; flag any change above 1 point |
| 6 | **UI honesty:** rename "JobBERT Match" to "Semantic Match"; add a "how this score is computed" tooltip | Removes the label trap | Done |
| 7 | **Polish:** update `README`, `PROJECT_GUIDE`, poster numbers, record a final demo video | Everything the examiner reads is true | Docs match `EVALUATION.md` |

### Day by day

| Date | Plan | Owner |
|---|---|---|
| Mon 2 Nov | **Viva.** Immediately after, write down every question asked and any feedback; share it with the team | all |
| Tue 3 | Item 1: label the 30 pairs; build `evaluate_ranking.py` and baselines. Item 2: experience fix | DL lead + QA; Backend |
| Wed 4 | Item 3: fuzzy matching and aliases; rerun `evaluate_dl.py`. Item 1: tune the 70/30 blend using 2 JDs, test on the third | DL lead; QA |
| Thu 5 | Item 4: build training pairs, fine-tune, evaluate on held-out | DL lead |
| Fri 6 | Item 5: bias test. Item 2: analytics fix. Item 6: UI label and tooltip | QA; Frontend |
| Sat 7 | Integrate only the winners, behind a flag. Full regression: both test files plus `evaluate_dl.py`. Update docs and poster. Record the demo video | all |
| Sun 8 | **Freeze at noon, no code changes after.** Full dress rehearsal with a mock viva; update the Q&A for the new features | all |
| Mon 9 | **Evaluation** | all |

### Risks
- Fine-tuning gives no gain, or overfits: report it honestly; the experiment still counts.
- Labelling disagreements: use two labellers and report agreement.
- Running out of time: items 1, 2 and 6 are the must-haves; 3, 4 and 5 are the stretch.
- A late change breaks the demo: the Sunday freeze exists for this. The demo uses only integrated, tested code.

### What to show on evaluation day
`EVALUATION.md` (all tables), the before/after demo story, the ranking benchmark, the fine-tune comparison, the bias
table, and a clear list of limitations. Each point answers a question the examiner has already shown they will ask.
