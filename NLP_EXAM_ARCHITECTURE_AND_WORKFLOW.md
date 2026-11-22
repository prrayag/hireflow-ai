# HireFlow AI — NLP Exam Guide

This guide explains the system architecture, workflow, NLP pipeline, models, dataset, training, evaluation and a complete worked example. It describes the current local implementation, including changes that may not yet be committed.

## 1. Project objective

HireFlow AI assists a recruiter in comparing a job description (JD) with a batch of resumes. It extracts document text, identifies candidate information, uses neural models to compare resume evidence with the JD, calculates a ranking score and shows the results in a dashboard.

The project is a **hybrid NLP system**: transformer neural networks are combined with explicit rules for skills, experience and qualifications. Its scores are review aids; they are not validated probabilities of job success.

## 2. Complete system architecture

```text
                         RECRUITER
                             │
                             ▼
                      React + Vite UI
            ┌────────────────┴──────────────────┐
            │                                   │
   Job description                         Resume batch
   • Pasted text                           • PDF / DOCX
   • PDF / DOCX                            • Images / TXT / ZIP
            │                                   │
            └────────────────┬──────────────────┘
                             ▼
                       Flask backend
                     POST /api/upload
                             │
          ┌──────────────────┴────────────────────┐
          │                                       │
 JD requirement extraction                  Resume text extraction
 • Required / preferred                     • PyMuPDF: PDF text
 • Responsibilities                         • python-docx: DOCX
 • Experience requirement                   • EasyOCR: images
                                                  │
                                                  ▼
                                      Rule-based metadata extraction
                                      • Skills, education, experience
                                      • Email and phone
                                                  │
                                                  ▼
                                       Section-aware chunking
                                                  │
                                                  ▼
                                     Sentence-BERT bi-encoder
                                      384-dimensional vectors
                                                  │
                          ┌───────────────────────┴──────────────────┐
                          ▼                                          ▼
                     MongoDB                                 In-memory fallback
                          └───────────────────────┬──────────────────┘
                                                  ▼
                                        Cosine similarity
                                                  │
                                                  ▼
                                      Candidate chunk aggregation
                                                  │
                                                  ▼
                                      MiniLM cross-encoder
                                      JD + resume evidence → logit
                                                  │
                                                  ▼
                                    Hybrid weighted ranking score
                                                  │
                                                  ▼
                                  Ranked dashboard, filters and CSV
```

| Layer | Technology | Responsibility |
|---|---|---|
| Frontend | React, Vite | Collect input and display results |
| API | Flask | Handle uploads and return JSON |
| Documents | PyMuPDF, python-docx, EasyOCR | Extract text |
| Preprocessing | Python and regular expressions | Identify sections and structured signals |
| Retrieval | Sentence-BERT | Produce embeddings |
| Reranking | Fine-tuned MiniLM cross-encoder | Score JD and candidate evidence together |
| Batch processing | PySpark | Parallelize chunk preparation for larger batches |
| Storage | MongoDB or Python memory | Store chunks and vectors |
| Training | PyTorch | Fine-tune model weights |

## 3. Complete application workflow

1. The recruiter pastes a JD or uploads a PDF/DOCX JD.
2. The recruiter uploads individual resumes or a ZIP archive.
3. The backend extracts text and assigns each readable resume an ID. Unreadable files are reported.
4. It identifies some requirements and candidate metadata with rules.
5. It divides resume text into section-aware chunks of up to approximately 90 words.
6. Sentence-BERT embeds the chunks in batches. For eight or more resumes, Spark can prepare chunks in parallel; model encoding occurs after collection in the main Python process.
7. The system stores chunks and embeddings in MongoDB, or in memory if MongoDB is unavailable.
8. It embeds the JD and compares it with resume chunks using cosine similarity.
9. It aggregates each candidate's strongest chunk similarities.
10. The cross-encoder jointly scores the JD and selected evidence for each candidate.
11. The backend combines semantic, reranker, skill and experience signals into an overall score, sorts candidates and returns explanations.
12. The dashboard displays results with search, filters, pagination and CSV export.

**PDF limitation:** the active PDF parser reads the text layer. It does not currently run OCR on scanned PDF pages. EasyOCR is used for uploaded images. DOCX paragraphs and tables are read, but complex layouts may not be fully captured.

## 4. NLP pipeline

```text
Document ingestion → text extraction → cleaning and section detection
→ rule-based metadata extraction → sentence-aware chunking → tokenization
→ transformer embeddings → cosine similarity → cross-encoder reranking
→ structured signals → weighted score → sorted output
```

### Text preparation

The system removes empty lines, normalizes whitespace and recognizes headings such as Summary, Experience, Skills, Projects, Education and Certifications. It groups sentences and bullet points into chunks, splitting exceptionally long pieces by word count.

The project does not apply a complete classical pipeline of stemming, lemmatization and stop-word removal. The transformer models use their own tokenizer and contextual representations.

### Tokenization

A tokenizer converts text into tokens and then numerical token IDs understood by a model. Tokens can represent complete words, subword pieces or punctuation. The cross-encoder receives the JD and resume evidence as a pair.

### Embeddings and cosine similarity

An embedding is a vector of numbers representing text. The Sentence-BERT model produces a normalized **384-dimensional vector**. Cosine similarity measures the angle between JD and resume vectors:

```text
cosine(A, B) = (A · B) / (||A|| × ||B||)
```

Higher values generally indicate closer semantic similarity. In this implementation negative chunk similarities are clipped to zero.

### Candidate aggregation

For each candidate, the system selects up to three highest-scoring chunks:

```text
semantic score = 100 × (0.65 × best similarity
                       + 0.35 × mean of top three similarities)
```

The selected chunks are also passed to the cross-encoder and returned as evidence. An evidence item can contain multiple sentences.

## 5. Neural models

### Sentence-BERT bi-encoder

**Model:** `sentence-transformers/all-MiniLM-L6-v2`  
**Role:** semantic retrieval  
**Output:** a 384-dimensional vector per text input.

```text
JD → encoder → JD vector
Resume chunk → encoder → chunk vector
Both vectors → cosine similarity
```

It is called a bi-encoder because the two texts are encoded independently. Resume embeddings can be stored for later use. This model is pretrained; it was not fine-tuned by the project training script.

### MiniLM cross-encoder

**Base model:** `cross-encoder/ms-marco-MiniLM-L-6-v2`  
**Local fine-tuned checkpoint:** `backend/model_artifacts/cross_encoder_v1/`  
**Local model version:** `hireflow-weakly-supervised-ranker-v1`.

The cross-encoder reads the JD and selected resume evidence together and produces a relevance **logit**. The application applies sigmoid and multiplies the result by 100:

```text
sigmoid(x) = 1 / (1 + e^(-x))
```

Processing both texts together allows attention to consider their interaction. It is more expensive per candidate than comparing precomputed vectors. If the cross-encoder cannot load, the application uses a bi-encoder scoring fallback.

### Transformer concepts

- **Transformer:** a neural architecture that creates contextual token representations using attention.
- **Self-attention:** allows tokens to influence the representation of other tokens in the model input.
- **Transfer learning:** starts with a pretrained model instead of random weights.
- **Fine-tuning:** updates pretrained weights using task-specific examples.
- **Logit:** an unrestricted raw model output; sigmoid maps it to the 0–1 interval.

## 6. Hybrid scoring

With the cross-encoder:

```text
Overall = 0.45 × semantic score
        + 0.40 × cross-encoder score
        + 0.10 × skills score
        + 0.05 × experience score
```

Without the cross-encoder:

```text
Overall = 0.80 × semantic score
        + 0.15 × skills score
        + 0.05 × experience score
```

If no skill score can be derived, semantic score is substituted for that component. If no experience requirement is detected, the current experience helper returns 100 for the formula, while the UI displays that no requirement was detected.

The qualification check is displayed separately and is **not part of the overall weighted formula**. These weights are hand-selected; the resulting percentage is a ranking score, not a calibrated hiring-success probability.

## 7. Training dataset

The project uses 100 synthetic resumes from `test_data/100_resumes.zip`. Each is paired with five job profiles: Python backend, machine learning, frontend, DevOps and Java full stack.

```text
100 resumes × 5 job descriptions = 500 resume–JD pairs
```

The labels are generated from skill overlap, rather than recruiter judgements. This is **weak supervision**:

| Skill coverage | Label | Description |
|---:|---:|---|
| 0% | 0 | Irrelevant |
| >0% and <25% | 1 | Weak |
| ≥25% and <50% | 2 | Good |
| ≥50% | 3 | Excellent |

Distribution: 124 label-0, 201 label-1, 131 label-2 and 44 label-3 pairs.

The split is by resume ID to prevent the same resume appearing in multiple splits:

| Split | Resumes | Pairs |
|---|---:|---:|
| Training | 70 | 350 |
| Validation | 15 | 75 |
| Test | 15 | 75 |

The same five job profiles occur across the splits. The test therefore checks held-out resumes for known job profiles; it does not test generalization to entirely unseen JDs.

## 8. Fine-tuning details

| Setting | Value |
|---|---|
| Base cross-encoder | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Training / validation pairs | 350 / 75 |
| Epochs | 2 |
| Batch size | 8 |
| Learning rate | 2e-5 |
| Optimizer | AdamW |
| Loss | BCEWithLogitsLoss |
| Training maximum length | 384 tokens |
| Gradient clipping | 1.0 |
| Random seed | 42 |
| Recorded device | CPU |

The labels are normalized to soft targets: 0 → 0.000, 1 → 0.333, 2 → 0.667, 3 → 1.000.

For each mini-batch, the tokenizer converts JD–resume pairs to tensors. A forward pass produces logits; `BCEWithLogitsLoss` compares them with targets; backpropagation calculates gradients; gradient clipping limits their magnitude; AdamW updates weights. The best validation-loss checkpoint is saved.

| Epoch | Training loss | Validation loss |
|---:|---:|---:|
| 1 | 0.6203 | 0.5037 |
| 2 | 0.5232 | 0.4462 |

Decreasing loss demonstrates improved agreement with these weak labels, not proven real-world hiring performance.

## 9. Recorded evaluation

The held-out set contains 75 pairs from 15 resumes and the five known job descriptions.

| Method | Precision@3 | Recall@5 | NDCG@5 | MRR |
|---|---:|---:|---:|---:|
| Skill-overlap baseline | 1.0000 | 0.9000 | 1.0000 | 1.0000 |
| Sentence-BERT | 0.6667 | 0.6067 | 0.7710 | 1.0000 |
| Pretrained cross-encoder | 0.8667 | 0.7533 | 0.8818 | 1.0000 |
| Fine-tuned cross-encoder | 1.0000 | 0.9000 | 1.0000 | 1.0000 |

Fine-tuned Spearman correlation with weak labels: **0.9397**.

- **Precision@3:** proportion of the top three results labelled relevant.
- **Recall@5:** proportion of relevant candidates retrieved in the top five.
- **NDCG@5:** ranking quality accounting for graded relevance and position.
- **MRR:** how early the first relevant candidate appears.
- **Spearman correlation:** agreement between model-score ordering and label ordering.

**Interpretation:** the skill baseline performs perfectly against labels constructed from the same skill-overlap rule, so this comparison is circular. The results show agreement with synthetic labels, not human-validated hiring accuracy. The recorded evaluator compares standalone model scores; it is not a full evaluation of the latest combined dashboard score.

### Name-masking stability

| Model | Mean score change | Maximum score change |
|---|---:|---:|
| Pretrained cross-encoder | 1.5401 points | 7.0905 points |
| Fine-tuned cross-encoder | 1.3358 points | 4.5543 points |

This single counterfactual test does not establish fairness across protected characteristics or real applicant populations.

## 10. Complete example: input to output

The numerical model scores below are **illustrative**, not measured model output. They show how the current formulas work.

### Input job description

```text
Role: Python Backend Developer
Required skills: Python, Flask, SQL, Docker
Experience: 4 years
Education: Bachelor's degree
Responsibilities: Build backend APIs and deploy services.
```

### Input resume

```text
Name: Asha Patel
Email: asha@example.com

SUMMARY
Backend developer with 3 years of experience.

SKILLS
Python, Flask, SQL, AWS.

EXPERIENCE
Built Python REST APIs using Flask.
Worked with SQL databases and deployed services on AWS.

EDUCATION
Bachelor's degree in Computer Science.
```

### A. Document and metadata extraction

For a PDF, PyMuPDF extracts the text layer. Rules can then identify an email, approximately three years of experience, a bachelor's degree and known skills Python, Flask, SQL and AWS. The actual displayed candidate name is derived from the uploaded filename.

The labelled JD can yield required skills Python, Flask, SQL and Docker, four years of experience and a responsibility about building APIs and deploying services. Extraction depends on JD formatting.

### B. Section-aware chunks

Conceptually, the resume is divided into summary, skills, experience and education chunks. Each chunk and the JD is encoded into a 384-dimensional vector.

Assume these cosine similarities:

```text
Summary:    0.60
Skills:     0.75
Experience: 0.85
Education:  0.35
```

Top three: 0.85, 0.75, 0.60. Their mean is 0.7333.

```text
semantic score = 100 × (0.65 × 0.85 + 0.35 × 0.7333)
               ≈ 80.92
```

### C. Cross-encoder

The JD and selected evidence chunks are scored jointly. If the illustrative logit is 1.386:

```text
sigmoid(1.386) ≈ 0.80 → reranker score 80.00
```

### D. Structured signals

```text
Skills: Python, Flask and SQL found; Docker not detected
Skill coverage = 3 / 4 × 100 = 75%

Experience: 3 years detected / 4 requested × 100 = 75%

Qualification: bachelor's degree detected in both → 100% check
```

“Not detected” means unverified; it does not prove the candidate lacks the requirement. The qualification check only compares broad degree levels.

### E. Final score

```text
0.45 × 80.92 = 36.414   semantic
0.40 × 80.00 = 32.000   cross-encoder
0.10 × 75.00 =  7.500   skills
0.05 × 75.00 =  3.750   experience
--------------------------------------
Overall       = 79.664 ≈ 79.66
```

The qualification check is displayed separately and is not included in this sum.

### F. Rank and response

If the other candidates scored 67.10 and 43.80, the descending order would be Asha, candidate B, candidate C. A simplified illustrative response:

```json
{
  "name": "Asha Patel",
  "ai_score": 79.66,
  "semantic_score": 80.92,
  "reranker_score": 80.0,
  "skills_score": 75.0,
  "experience_score": 75.0,
  "qualification_score": 100.0,
  "matched_skills": ["Python", "Flask", "SQL"],
  "missing_skills": ["Docker"],
  "relevant_sentences": ["Built Python REST APIs using Flask."],
  "inference_mode": "bi-encoder+cross-encoder",
  "model_version": "hireflow-weakly-supervised-ranker-v1"
}
```

The actual API includes additional fields, and selected evidence items can contain multiple sentences.

## 11. Which parts are neural?

| Function | Method |
|---|---|
| Image OCR | Pretrained EasyOCR neural models |
| Sentence embeddings | Pretrained Sentence-BERT transformer |
| Vector comparison | Cosine-similarity formula |
| Joint JD–resume scoring | Fine-tuned MiniLM cross-encoder |
| Skill aliases | Dictionary and rules |
| JD requirements | Heuristics and regular expressions |
| Experience and qualification checks | Rules and regular expressions |
| Final score | Fixed weighted formula |
| Ranking | Descending sort |

## 12. Limitations and future work

- Training labels are synthetic skill-overlap labels, not independent recruiter judgements.
- Resumes and job profiles are mostly IT-oriented; cross-domain performance has not been established.
- The five test JDs are seen during training, and synthetic resumes share templates.
- Requirement extraction, experience parsing and degree checks are heuristic.
- Scanned PDF OCR and complex layout handling need improvement.
- Qualification checks do not contribute to the final score and do not verify degree fields or equivalence.
- Scores are not calibrated probabilities; name masking alone does not establish fairness.
- A human should review evidence and make the final decision.

Next research steps: collect independent human labels across multiple domains, measure reviewer agreement, evaluate on unseen resumes **and unseen JDs**, improve parsing and requirement-level evidence, and report ranking and fairness results with their limitations.

## 13. Short viva answer

> HireFlow AI is a hybrid NLP resume-screening system. It extracts resume text, divides it into sections and chunks, and uses a Sentence-BERT bi-encoder to produce 384-dimensional embeddings. It compares job descriptions and resume chunks with cosine similarity. A MiniLM cross-encoder, fine-tuned on weakly labelled resume–JD pairs, jointly scores the JD and selected evidence. The system combines semantic relevance with skill and experience signals, ranks candidates, and displays scores and evidence. The current benchmark uses synthetic labels, so it measures agreement with the labelling rule rather than real-world hiring accuracy.

## 14. Implementation files

- `backend/app.py` — upload API, parsing and response.
- `backend/dl_pipeline.py` — chunking and rule-based feature extraction.
- `backend/processor.py` — embeddings, reranking and scoring.
- `backend/training/prepare_dataset.py` — weak-label dataset creation.
- `backend/training/train_cross_encoder.py` — PyTorch fine-tuning.
- `backend/training/evaluate.py` — evaluation and name-masking test.
- `backend/training/data/metadata.json` — dataset provenance.
- `backend/training/results/evaluation.json` — recorded metrics.
- `frontend/src/pages/DashboardPage.jsx` — input and ranked results.
