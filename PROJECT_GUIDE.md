# HireFlow AI — Complete Project Guide
> Read this top to bottom. Every concept is explained simply so you can answer any professor question.

---

## 1. What Is This Project?

HireFlow AI is an **AI-powered resume screening system**. You upload resumes, and the system:
1. **Reads** the text from each resume (PDF or DOCX)
2. **Extracts** structured info — name, email, skills, experience, education
3. **Scores** each candidate out of 100 using 3 AI components
4. **Ranks** them and shows a dashboard

The problem it solves: HR teams get 500 resumes for 1 job. Reading all of them manually takes days. HireFlow does it in seconds.

---

## 2. System Architecture (Big Picture)

```
[User uploads resumes via browser]
          ↓
   [React Frontend] ←→ [Flask Backend API]
                              ↓
                    [Resume Parser]     ← reads PDF/DOCX/images
                              ↓
                    [Feature Extractor] ← pulls name, skills, exp
                              ↓
                    [AI Scorer]         ← 3 components → score/100
                              ↓
                    [MongoDB Atlas]     ← stores all results
                              ↓
             [Analytics Page]          ← matplotlib charts from live DB
```

---

## 3. The Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Frontend | React + Vite | Fast, component-based UI |
| Backend | Flask (Python) | Lightweight API server |
| Database | MongoDB Atlas | Stores candidate documents |
| ML Model | TabTransformer (PyTorch) | Neural network for scoring |
| Text similarity | scikit-learn TF-IDF | Keyword overlap scoring |
| Charts | matplotlib (server-side) | Generated as PNG images |
| Text extraction | PyMuPDF, python-docx, easyOCR | Read any resume format |

---

## 4. The AI Pipeline — Step by Step

### Step 1: Parsing the Resume

When you upload a PDF, we use **PyMuPDF (fitz)** to extract raw text.
```
PDF file → fitz.open() → page.get_text() → raw string of text
```
If the PDF is a scanned image (no text layer), we run **OCR** using **easyOCR** — it looks at pixels and recognises letters, just like how you'd read a photograph of a document.

For DOCX files, we use **python-docx** which reads the XML structure inside the .docx zip file.

### Step 2: Feature Extraction (`resume_features.py`)

From the raw text, we extract structured fields using **Regular Expressions (regex)**.

**What is a regex?**
A pattern that searches text. Example: `r'[\w.]+@[\w.]+\.\w+'` finds email addresses.

| Field | How extracted |
|-------|--------------|
| Email | Regex: looks for `@` with text around it |
| Phone | Regex: looks for `+91` followed by 10 digits |
| Experience years | Regex: finds date ranges like "Jan 2020 – Present", calculates duration |
| Education | Regex: looks for keywords like "B.Tech", "M.Tech", "MBA" then grabs that line |
| Skills | Regex: finds a "SKILLS" section, then splits by commas/bullets |
| Department | Keyword matching: if text has "kubernetes/docker/python" → IT dept |

### Step 3: Scoring — The 3 AI Components

Every candidate gets a score out of **100**, split across 3 components:

```
Total Score = TabTransformer (0-40) + Vector Similarity (0-35) + TF-IDF (0-25)
```

---

## 5. Component 1: TabTransformer (0–40 points)

### What is a Transformer?

A Transformer is a type of neural network that was originally invented for language tasks (like ChatGPT). The key idea is the **attention mechanism** — the model learns which inputs to "pay attention to" when making predictions.

**TabTransformer** is a Transformer adapted for **tabular data** (tables with rows and columns) instead of text.

### How it works in HireFlow

**Input features (what we feed the model):**
- `experience_years` — how many years of work experience
- `skills_count` — how many skills listed
- `department` — IT, Finance, HR, Marketing, Sales (categorical)
- `job_role` — Software Engineer, Data Scientist, etc. (categorical)

**Categorical Encoding:**
Raw text like "IT" can't go into a neural network. So we use a `LabelEncoder`:
```
"IT" → 2
"Finance" → 0
"HR" → 1
```
This is stored in `label_encoders.pkl`.

**Embeddings:**
Each category gets converted to a **vector** (a list of numbers). "IT" might become `[0.2, -0.5, 0.8, ...]` (32 numbers). This is called an embedding. Similar categories end up with similar vectors.

**Transformer layers:**
The model has 2 Transformer layers with 4 attention heads. Each head learns a different "aspect" of the relationship between features. For example, one head might learn "high experience + IT = high score."

**Output:**
A single number between 0 and 1, multiplied by 40 → TabTransformer score.

**Why TabTransformer and not just a formula?**
A formula is fixed. A neural network *learns* the patterns from data. Our model was trained on 1000 candidate records and learned which combinations of features correlate with good candidates.

### Training (already done, model saved as `tab_transformer.pth`)

```python
# Training loop (simplified)
for epoch in range(100):
    predictions = model(X_train)       # forward pass
    loss = criterion(predictions, y)   # compare to true labels
    loss.backward()                    # backpropagation
    optimizer.step()                   # update weights
```

The model file `tab_transformer.pth` stores all the learned weights (numbers). We load this file at startup and use it for every new resume — we never retrain during the app.

---

## 6. Component 2: Vector Similarity (0–35 points)

### Only works when a Job Description (JD) is provided

**With JD:**
1. Convert the candidate's resume text into a **vector** (a list of numbers) using word embeddings
2. Convert the JD into a vector the same way
3. Compute **cosine similarity** between the two vectors

**What is cosine similarity?**
Two vectors point in different directions in multi-dimensional space. Cosine similarity measures the angle between them:
- Angle = 0° → similarity = 1.0 (identical direction → perfect match)
- Angle = 90° → similarity = 0.0 (no relation)
- Angle = 180° → similarity = -1.0 (opposite)

```python
similarity = dot(resume_vec, jd_vec) / (|resume_vec| × |jd_vec|)
```

**Without JD:**
We can't compare to nothing. So we compute a "profile richness" score instead:
```python
composite = (skills_signal × 0.35) + (education × 0.25) + (experience × 0.20)
             + (contact_info × 0.10) + (keyword_density × 0.10)
vec_score = composite × 35
```

---

## 7. Component 3: TF-IDF Match (0–25 points)

### What is TF-IDF?

TF-IDF stands for **Term Frequency – Inverse Document Frequency**. It's a classic information retrieval technique from the 1970s, still widely used.

**Term Frequency (TF):**
How often does a word appear in THIS document?
```
TF("python", resume) = count of "python" in resume / total words in resume
```

**Inverse Document Frequency (IDF):**
How rare is this word across ALL documents?
```
IDF("python") = log(total documents / documents containing "python")
```
Common words like "the", "and" get a low IDF (they're in every doc).
Rare words like "kubernetes" get a high IDF (they're specific and meaningful).

**TF-IDF:**
```
TF-IDF("python") = TF × IDF
```
High score = the word appears often in THIS resume AND is rare across all resumes.

**In HireFlow:**
We represent both the resume and the JD as TF-IDF vectors, then compute cosine similarity between them. A resume that uses the same specific technical words as the JD gets a high score.

```python
from sklearn.feature_extraction.text import TfidfVectorizer
vectorizer = TfidfVectorizer()
matrix = vectorizer.fit_transform([resume_text, jd_text])
similarity = cosine_similarity(matrix[0], matrix[1])[0][0]
tfidf_score = similarity × 25
```

---

## 8. Anomaly Detection

After scoring, we flag candidates that look statistically unusual using **Isolation Forest**.

**What is Isolation Forest?**
An unsupervised ML algorithm. The idea: anomalies are easier to isolate. If you randomly split data, an outlier gets isolated in fewer splits than a normal point.

**What makes a candidate an anomaly in our system?**
- Very high score but very few skills (suspicious)
- Huge experience but no education mentioned
- Text length is an extreme outlier (too short = fake, too long = copy-paste dump)

Flagged candidates show a ⚠️ Flagged badge on the dashboard.

---

## 9. MongoDB — Why We Use It

MongoDB is a **NoSQL document database**. Instead of SQL tables with fixed columns, it stores JSON-like documents.

**Why not SQL?**
Each resume produces a different set of fields. A software engineer has "frameworks" but an HR manager doesn't. MongoDB handles variable structure naturally.

**Each candidate document looks like:**
```json
{
  "name": "Arjun Mehta",
  "score": 90.2,
  "tab_transformer_score": 30.2,
  "vector_similarity_score": 35.0,
  "tfidf_score": 25.0,
  "skills": ["python", "docker", "kubernetes"],
  "experience_years": 6,
  "batch_id": "abc123",
  "uploaded_at": "2026-05-01T08:00:00Z"
}
```

**Indexes:**
We created indexes on `uploaded_at` and `batch_id` so MongoDB can find the latest batch in milliseconds instead of scanning all 384 documents.

---

## 10. Big Data — Apache Spark

### Why Spark?

Our system processes resumes one at a time. But what if a company uploads **1 million resumes**? A single machine can't handle that in reasonable time.

Apache Spark is a **distributed computing engine** — it splits work across many machines (a cluster) and processes data in parallel.

### Core Concepts

**RDD (Resilient Distributed Dataset)**
The fundamental data structure in Spark. An RDD is an immutable, distributed collection of objects split across multiple machines.

```python
# Create an RDD from a list
rdd = sc.parallelize([1, 2, 3, 4, 5])

# Each item is processed on a different machine
```

**Transformations vs Actions:**

| Type | What | Example | When it runs |
|------|------|---------|-------------|
| Transformation | Creates a new RDD | `.map()`, `.filter()`, `.flatMap()` | **Lazy** — not yet |
| Action | Triggers computation | `.count()`, `.collect()`, `.saveAsTextFile()` | **Now** — executes everything |

**This is the key insight:** Spark builds up a recipe (the DAG) but doesn't cook anything until you say "go" with an action.

**DAG (Directed Acyclic Graph)**
When you chain transformations, Spark builds a graph:
```
raw_data_rdd
    ↓ .map(parse_resume)
parsed_rdd
    ↓ .filter(has_email)
valid_rdd
    ↓ .map(score_candidate)
scored_rdd
    ↓ .sortBy(score, descending=True)   ← .collect() triggers everything
```
This graph is the DAG. "Directed" = flows one way. "Acyclic" = no loops.

**Stage:**
Spark divides the DAG into **stages**. A new stage starts whenever data needs to be **shuffled** (moved between machines). This happens at:
- `groupByKey()` — groups records by key, data must move to the right machine
- `reduceByKey()` — same
- `join()` — joining two RDDs requires shuffling

Within one stage, all operations run on local data (fast). Between stages, data moves over the network (slower).

**Job:**
One Spark **job** = one action call. Each job generates its own DAG.

```
Job 1: raw_rdd → parse → filter → .count()           # 2 stages
Job 2: parsed_rdd → tfidf → .reduceByKey() → .collect()  # 3 stages (shuffle at reduceByKey)
Job 3: scored_rdd → .sortBy() → .saveAsTextFile()    # 2 stages
```

**Task:**
One **task** = one partition processed by one core on one machine. If your data has 8 partitions and 4 machines with 2 cores each → 8 tasks run in parallel.

### Our Spark Pipeline for HireFlow

**Job 1 — Ingest & Clean:**
```python
raw_rdd = sc.textFile("hdfs://localhost:9000/hireflow/resumes.csv")
# Stage 1: read → parse each line → filter out empty rows
parsed_rdd = raw_rdd.map(parse_line).filter(is_valid)
parsed_rdd.cache()  # keep in memory for reuse
count = parsed_rdd.count()  # ACTION → triggers Job 1
```

**Job 2 — TF-IDF Feature Extraction:**
```python
# flatMap: one resume → many (word, 1) pairs
word_pairs = parsed_rdd.flatMap(tokenize_skills)
# reduceByKey: shuffle! → new stage
term_freq = word_pairs.reduceByKey(lambda a, b: a + b)
# join: another shuffle! → new stage
tfidf_rdd = term_freq.join(idf_rdd).map(compute_tfidf)
tfidf_rdd.collect()  # ACTION → triggers Job 2 (3 stages)
```

**Job 3 — Score & Rank:**
```python
scored_rdd = parsed_rdd.map(score_candidate)
ranked_rdd = scored_rdd.sortBy(lambda x: x['score'], ascending=False)
ranked_rdd.saveAsTextFile("hdfs://output/ranked/")  # ACTION → Job 3
```

**Job 4 — Analytics:**
```python
# Score band histogram
bands = scored_rdd.map(to_band).reduceByKey(lambda a,b: a+b)  # shuffle
# Avg score by department
dept_scores = scored_rdd.map(lambda x: (x['dept'], x['score']))
dept_avg = dept_scores.groupByKey().mapValues(average)  # shuffle
dept_avg.collect()  # ACTION → Job 4 (3 stages)
```

---

## 11. Hadoop & HDFS

### What is HDFS?

HDFS stands for **Hadoop Distributed File System**. It stores large files across multiple machines.

**How it works:**
1. You store a 10GB CSV file in HDFS
2. HDFS splits it into **blocks** (default 128MB each)
3. Each block is stored on 3 different machines (replication factor = 3)
4. If one machine dies, the data still exists on 2 other machines → **fault tolerant**

**Components:**
- **NameNode** — the master. Keeps track of which blocks are where. Does NOT store data.
- **DataNode** — the workers. Actually store the data blocks.

```
Client → NameNode: "Where is file resumes.csv?"
NameNode → Client: "Blocks 1,2,3 are on DataNode-2 and DataNode-5"
Client → DataNode-2: "Give me block 1"
```

**In our project:**
```bash
# Upload dataset to HDFS
hdfs dfs -put resumes.csv /hireflow/input/

# Read in Spark
rdd = sc.textFile("hdfs://localhost:9000/hireflow/input/resumes.csv")
```

Spark reads directly from HDFS — each Spark executor preferably runs on the same machine that holds its partition's block. This is **data locality** — move the computation to the data, not the data to the computation.

### MapReduce vs Spark

Your professor will ask this:

| Feature | Hadoop MapReduce | Apache Spark |
|---------|-----------------|-------------|
| Speed | Slow — writes to disk after every step | Fast — keeps data in RAM (100x faster) |
| Model | Map → Reduce only | Map, Reduce, Filter, Join, Sort, etc. |
| Language | Java primarily | Python, Scala, Java, R |
| Iterative tasks | Bad — reads disk every iteration | Great — cache RDD in memory |
| Real-time | No | Yes (Spark Streaming) |

Spark replaced MapReduce for most use cases but still uses HDFS for storage.

---

## 12. Q&A — Professor Questions

**Q: What is the difference between a transformation and an action in Spark?**

A: A transformation (like `.map()` or `.filter()`) creates a new RDD but does NOT execute immediately — Spark is lazy. An action (like `.count()` or `.collect()`) triggers actual execution of all queued transformations. This lazy evaluation lets Spark optimise the entire computation plan before running it.

---

**Q: What is a DAG in Spark and why is it useful?**

A: When you chain transformations, Spark builds a Directed Acyclic Graph — a map of all the operations to perform. It's "directed" because data flows one way, "acyclic" because there are no loops. The DAG is useful because Spark can optimise it: reorder operations, skip redundant steps, and decide where to place computation. You can view it live at http://localhost:4040.

---

**Q: What causes a new stage in Spark?**

A: A shuffle. Whenever data from one partition needs to go to a different partition — which happens with `groupByKey()`, `reduceByKey()`, `join()`, `sortBy()` — Spark must redistribute data across the network. This marks the boundary between stages. Within a stage, all operations are "narrow" (each partition processes its own data independently).

---

**Q: What is TF-IDF and why is it used for resume matching?**

A: TF-IDF scores each word by how important it is to a specific document relative to the whole collection. A word like "Python" that appears 10 times in a resume but rarely in other resumes gets a high TF-IDF score. We vectorize both the resume and the job description using TF-IDF, then compute cosine similarity between the two vectors. A high similarity means the resume uses the same important keywords as the JD.

---

**Q: Why use a Transformer model (TabTransformer) instead of a simple formula?**

A: A formula is static — you decide the weights yourself. A neural network *learns* the weights from data. The TabTransformer was trained on 1000 labelled candidates and learned that, for example, a DevOps engineer with 5 years + Kubernetes + AWS scores differently than an HR manager with 5 years + Excel. A hardcoded formula couldn't capture that nuance. The attention mechanism specifically lets the model learn *interactions* between features.

---

**Q: Why MongoDB and not SQL?**

A: Each resume produces a different structure. A software engineer has "frameworks" and "cloud skills", an HR manager has "ATS tools" and "compliance knowledge". SQL requires fixed columns — you'd need 50 optional NULL columns. MongoDB stores each candidate as a JSON document, so every candidate can have exactly the fields that apply to them, no more, no less.

---

**Q: What is an RDD?**

A: Resilient Distributed Dataset. It's Spark's core abstraction — an immutable, fault-tolerant collection of objects distributed across a cluster. "Resilient" means if a machine fails, Spark can recompute the lost partition from its lineage (the chain of transformations that created it). You create RDDs from files, databases, or other RDDs via transformations.

---

**Q: What is the difference between `groupByKey` and `reduceByKey`?**

A: Both group records by key. `groupByKey` collects ALL values for each key into a list, then you process the list. This shuffles all data over the network first. `reduceByKey` applies the reduction function locally on each partition first (partial aggregation), THEN shuffles and combines. For counting or summing, `reduceByKey` is much faster because it sends less data over the network.

---

**Q: What is HDFS replication and why does it matter?**

A: HDFS stores each block of data on 3 different DataNodes by default. If one machine crashes, the data is still available on the other 2. This is fault tolerance — a critical property for big data systems where you're running hundreds of machines and hardware failures are normal, not exceptional.

---

**Q: How does HireFlow's big data pipeline integrate with HDFS and Spark?**

A: The resume dataset (CSV with candidate records) is uploaded to HDFS using `hdfs dfs -put`. Spark reads it directly from HDFS — `sc.textFile("hdfs://...")` — which splits the file into partitions aligned with HDFS blocks. Spark processes them in parallel: Job 1 cleans the data, Job 2 extracts TF-IDF features (with a shuffle for `reduceByKey`), Job 3 scores and ranks (shuffle for `sortBy`), Job 4 computes analytics aggregations (two shuffles → 3 stages). Results are written back to HDFS and also pushed to MongoDB for the live dashboard.

---

**Q: What is anomaly detection and how does Isolation Forest work?**

A: Anomaly detection finds data points that are statistically unusual. We use Isolation Forest — it randomly splits the feature space (score, text length, skill count) using random cuts. Normal points are deep in the tree (take many cuts to isolate). Anomalies are shallow (isolated in few cuts). A candidate with a very high score but almost no skills would be flagged — likely a resume padded with keywords.

---

## 13. File-by-File Reference

| File | What it does |
|------|-------------|
| `backend/app.py` | Flask API: upload endpoint, /results, /api/charts, /api/big-data-stats |
| `backend/resume_parser.py` | Reads PDF (PyMuPDF), DOCX (python-docx), images (easyOCR) |
| `backend/resume_features.py` | Extracts name, email, phone, skills, experience, education using regex |
| `backend/candidate_scorer.py` | Runs TabTransformer + TF-IDF + Vector scoring, anomaly detection |
| `backend/json_storage.py` | Saves results to local JSON and pushes to MongoDB |
| `backend/config.py` | MongoDB connection string |
| `backend/tab_transformer.pth` | Trained model weights (PyTorch) |
| `backend/label_encoders.pkl` | LabelEncoder for Department and JobRole categories |
| `backend/model_config.json` | Architecture: embedding_dim=32, heads=4, layers=2 |
| `frontend/src/pages/Dashboard.jsx` | Candidate rankings table with score breakdown |
| `frontend/src/pages/AnalyticsPage.jsx` | Fetches matplotlib chart images from backend |
| `frontend/src/pages/UploadPage.jsx` | Drag-and-drop file upload with JD text area |
| `frontend/src/components/CandidateTable.jsx` | Expandable rows, skill highlighting, score bars |
| `generate_test_resumes.py` | Creates 10 realistic test resumes (PDF + DOCX) |

---

## 14. Data Flow Summary

```
[Resume uploaded]
       ↓
parse_resume() → raw text string
       ↓
extract_candidate_info() → {name, email, phone, skills, exp, edu, dept, role}
       ↓
get_matched_skills() → list of known skills found in text
       ↓
_load_models() → loads TabTransformer + LabelEncoders
       ↓
_get_tab_score() → neural net forward pass → 0 to 40
       ↓
if JD provided:
  _get_candidate_embedding() + _get_jd_embedding() → vectors
  cosine_similarity() → 0 to 35
  TfidfVectorizer().fit_transform() + cosine_similarity() → 0 to 25
else:
  profile_richness_formula() → 0 to 35
  profile_richness_formula() × 25/35 → 0 to 25
       ↓
total_score = tab + vec + tfidf (max 100)
       ↓
shortlisted = score >= 60
       ↓
Isolation Forest → is_anomaly = True/False
       ↓
save_to_json() + MongoDB insert
       ↓
Dashboard shows ranked results
       ↓
/api/charts → matplotlib generates 4 PNG charts from MongoDB data
```

---

*This document covers everything needed to explain HireFlow AI to a professor in AI or Big Data subjects. Every component has a reason. Nothing is random.*
