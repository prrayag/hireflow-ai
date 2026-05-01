# HireFlow AI — Artificial Intelligence Deep Dive
> Everything about the AI in this project. Read this for your AI subject viva/presentation.

---

## 1. The Three AI Components at a Glance

HireFlow scores every resume out of **100** using three separate AI techniques stacked together:

```
┌─────────────────────────────────────────────────────────┐
│                  TOTAL SCORE (out of 100)               │
├───────────────────┬─────────────────┬───────────────────┤
│  TabTransformer   │ Vector Similarity│   TF-IDF Match    │
│    0  to  40      │    0  to  35     │    0  to  25      │
│  Neural Network   │ Embedding Match  │  Keyword Overlap  │
│  (Deep Learning)  │  (Semantic AI)   │  (Classic ML)     │
└───────────────────┴─────────────────┴───────────────────┘
```

Each component uses a fundamentally different AI technique. Together they are more robust than any single approach.

---

## 2. Machine Learning — The Foundation

Before going into each component, understand the basics.

### What is Machine Learning?

Traditional programming:
```
Rules + Data → Output
```

Machine Learning:
```
Data + Output → Rules (learned automatically)
```

You show the algorithm thousands of examples. It figures out the pattern itself.

### Types of ML used in HireFlow

| Type | Used for | How |
|------|---------|-----|
| **Supervised Learning** | TabTransformer scoring | Trained on labelled candidates (input features → expected score) |
| **Unsupervised Learning** | Anomaly Detection | No labels — finds outliers on its own |
| **Classical ML** | TF-IDF | No training needed — pure math formula |

---

## 3. Component 1 — TabTransformer (Deep Learning)

### 3.1 What Problem It Solves

Given structured data about a candidate (experience, skills, department, role), predict how strong they are — **without a job description**.

It answers: *"Is this person a strong candidate in general?"*

### 3.2 What is a Neural Network?

A neural network is layers of mathematical functions chained together:

```
Input Layer          Hidden Layers          Output Layer
[experience=5]  →   [neurons do math]  →   [score: 0.7]
[skills=10]
[dept=IT]
[role=Engineer]
```

Each connection between neurons has a **weight** — a number. During training, these weights are adjusted thousands of times until the output matches the expected answer.

### 3.3 What Makes a Transformer Special?

A standard neural network treats all inputs equally. A **Transformer** uses **Attention** — it learns which inputs matter more *in relation to each other*.

Example:
- "5 years experience" alone = moderately good
- "5 years experience" + "role: Senior Engineer" = very good
- "5 years experience" + "role: Fresher" = contradictory (suspicious)

The attention mechanism captures these relationships. It asks: *"Which other features should I pay attention to, when I'm processing this feature?"*

**Attention formula:**
```
Attention(Q, K, V) = softmax(QKᵀ / √d) × V
```
Where:
- Q = Query: what am I looking for?
- K = Key: what do the other features say about themselves?
- V = Value: what information do they actually carry?
- √d = scaling factor to prevent extremely large values

You don't need to memorise the formula — just know it lets the model learn *relationships* between input features.

### 3.4 Multi-Head Attention

Our model uses **4 attention heads**. Each head learns a different type of relationship:

```
Head 1 → learns: experience × skills interactions
Head 2 → learns: department × role interactions  
Head 3 → learns: experience × role interactions
Head 4 → learns: combined signal
```

All 4 heads run in parallel, then their outputs are concatenated and projected.

### 3.5 Why TabTransformer for Tabular Data?

Normal Transformers (like BERT) work on **text tokens**. TabTransformer adapts this for **tables**:

- **Categorical columns** (department, job_role) → each category gets an **embedding** (a learned vector)
- **Numerical columns** (experience_years, skills_count) → passed through directly
- All columns are processed together through the Transformer layers

This is more powerful than a standard decision tree or linear regression because it captures non-linear interactions between features.

### 3.6 The Architecture (our exact model)

```
model_config.json tells us:
  embedding_dim  = 32     ← each category encoded as 32 numbers
  num_heads      = 4      ← 4 attention heads
  num_layers     = 2      ← 2 Transformer blocks stacked
  num_cat_features = 2    ← Department, JobRole
  num_num_features = 2    ← experience_years, skills_count
  cat_vocab_sizes = [5, 28] ← 5 departments, 28 job roles
```

**Forward pass (what happens for one resume):**

```
Step 1: Encode categoricals
  "IT"              → embedding → [0.2, -0.5, 0.8, ..., 0.3]  (32 numbers)
  "Software Engineer" → embedding → [0.7, 0.1, -0.2, ..., 0.9]  (32 numbers)

Step 2: Combine with numericals
  experience_years = 5  → [5.0]
  skills_count = 10     → [10.0]
  All combined → one big vector

Step 3: Pass through 2 Transformer layers
  Layer 1: Self-attention + Feed-forward network
  Layer 2: Self-attention + Feed-forward network

Step 4: Output head
  Final vector → Linear layer → sigmoid → single number 0–1
  Multiply by 40 → TabTransformer score
```

### 3.7 Training Process

**Dataset:** ~1000 candidate records from an IBM HR Analytics dataset

**Features used:**
- Department (categorical): IT, Finance, HR, Marketing, Sales
- JobRole (categorical): 28 different roles
- YearsAtCompany (numerical) → mapped to experience_years
- Number of skills (numerical) → skills_count

**Labels:** Attrition/performance score normalised to 0–1

**Training loop:**
```python
model = TabTransformerModel(config)
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
criterion = nn.MSELoss()  # Mean Squared Error

for epoch in range(100):
    model.train()
    predictions = model(X_cat_train, X_num_train)  # forward pass
    loss = criterion(predictions.squeeze(), y_train) # how wrong?
    
    optimizer.zero_grad()  # reset gradients
    loss.backward()        # backpropagation: compute gradients
    optimizer.step()       # update weights: move in direction that reduces loss
```

**Backpropagation** is the core algorithm: it calculates how much each weight contributed to the error, then adjusts all weights slightly in the direction that reduces the error. Done millions of times = the model learns.

**Result:** Model saved to `tab_transformer.pth` — a file containing all learned weight matrices.

### 3.8 At Inference Time (when you upload a resume)

```python
# Load once at startup
model.load_state_dict(torch.load("tab_transformer.pth"))
model.eval()  # turn off dropout/batch norm

# For each resume:
dept_encoded = label_encoder["Department"].transform([dept])[0]  # "IT" → 2
role_encoded = label_encoder["JobRole"].transform([role])[0]     # "SE" → 23

X_cat = torch.tensor([[dept_encoded, role_encoded]])
X_num = torch.tensor([[experience_years, skills_count]])

with torch.no_grad():          # no gradient tracking needed
    raw_output = model(X_cat, X_num)  # forward pass only
    tab_score = raw_output.item() * 40  # scale to 0–40
```

No retraining. The model's weights are frozen. We just use the patterns it learned.

---

## 4. Component 2 — Vector Similarity (Semantic AI)

### 4.1 What Problem It Solves

Given a Job Description and a resume, how *semantically similar* are they?

Traditional keyword matching misses synonyms:
- JD says "ML Engineer" — resume says "Machine Learning Developer" → keyword miss
- Vector similarity catches this because similar concepts have similar vectors

### 4.2 Word Embeddings

A **word embedding** maps words to vectors in high-dimensional space so that semantically similar words are geometrically close:

```
"Python"     → [0.72, -0.15, 0.89, ..., 0.34]  (300 numbers)
"Django"     → [0.68, -0.22, 0.91, ..., 0.28]  ← close to Python (web framework)
"Kubernetes" → [0.55,  0.70, 0.22, ..., 0.61]  ← close to Docker (containers)
"Excel"      → [-0.2,  0.15, -0.4, ..., 0.80]  ← far from Python (different domain)
```

This is why vector similarity finds *meaning*, not just keyword overlap.

### 4.3 Document Embedding

To embed an entire resume (not just one word), we average the word embeddings:

```python
def embed_text(text):
    words = text.lower().split()
    vectors = [word2vec[w] for w in words if w in word2vec]
    if not vectors:
        return np.zeros(300)
    return np.mean(vectors, axis=0)  # average all word vectors
```

This gives one 300-dimensional vector representing the entire resume.

### 4.4 Cosine Similarity

Once we have two vectors (resume embedding and JD embedding), we measure their similarity:

```
               resume · jd
similarity = ─────────────────
             |resume| × |jd|
```

- `·` = dot product (multiply element-wise, sum up)
- `|v|` = magnitude (length) of vector

**Why cosine and not Euclidean distance?**
Because we care about *direction*, not length. A short resume and a long resume about the same topic should have similar vectors — cosine measures the angle between them, which captures topic similarity regardless of document length.

```
Result: 0.0 to 1.0 → multiply by 35 → Vector Similarity score
```

### 4.5 When There Is No JD

You can't compute similarity to nothing. So we fall back to a **profile richness composite**:

```python
composite = (
    skills_signal     × 0.35 +  # how many skills (cap at 20)
    education_signal  × 0.25 +  # PhD=1.0, MBA=0.85, BTech=0.7
    experience_signal × 0.20 +  # years/10, cap at 1.0
    contact_signal    × 0.10 +  # has email + phone = 1.0
    keyword_density   × 0.10    # known skills found / 15
)
composite = min(composite + 0.20, 1.0)  # baseline boost
vec_score = composite × 35
```

This is not vector similarity — it's an estimate of how strong the profile is. The label on the dashboard changes to reflect this.

---

## 5. Component 3 — TF-IDF (Classical Machine Learning)

### 5.1 What Problem It Solves

Given a resume and a JD, how many of the *important words* from the JD appear in the resume?

This is different from vector similarity:
- Vector similarity: understands meaning
- TF-IDF: measures exact keyword relevance

Both together = more robust than either alone.

### 5.2 Term Frequency (TF)

*How often does this word appear in THIS document?*

```
TF(word, document) = (number of times word appears) / (total words in document)
```

Example:
```
Resume has 200 words. "Python" appears 5 times.
TF("python", resume) = 5/200 = 0.025
```

Normalising by document length means long resumes don't automatically win.

### 5.3 Inverse Document Frequency (IDF)

*How rare is this word across ALL documents?*

```
IDF(word) = log(total_documents / documents_containing_word)
```

Example (with 1000 resumes total):
```
"the"    appears in 1000 docs → IDF = log(1000/1000) = log(1) = 0.0   (useless)
"python" appears in 400 docs  → IDF = log(1000/400) = 0.92            (somewhat useful)
"dask"   appears in 10 docs   → IDF = log(1000/10) = 2.0              (very distinctive)
```

Common words get IDF=0 (filtered out). Rare, specific words get high IDF (weighted more).

### 5.4 TF-IDF Score

```
TF-IDF(word, document, corpus) = TF × IDF
```

High TF-IDF = the word appears often in THIS document AND is rare across all documents.

### 5.5 Implementation in HireFlow

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def get_tfidf_score(resume_text, jd_text):
    vectorizer = TfidfVectorizer(
        stop_words='english',  # ignore "the", "and", "is"...
        max_features=5000      # top 5000 most informative words
    )
    # Fit on both documents together, transform each
    tfidf_matrix = vectorizer.fit_transform([resume_text, jd_text])
    
    # Row 0 = resume vector, Row 1 = JD vector
    similarity = cosine_similarity(tfidf_matrix[0], tfidf_matrix[1])[0][0]
    
    return round(similarity * 25, 1)  # scale to 0–25
```

**What `fit_transform` does:**
1. Builds vocabulary from both texts combined
2. Computes TF-IDF score for every word in every document
3. Returns a matrix where each row is a document, each column is a word's TF-IDF score

The resulting vectors are sparse (most words appear in only one document, so most values are 0).

### 5.6 Why Keep TF-IDF When We Have Vectors?

| Scenario | Vector Similarity | TF-IDF |
|----------|-----------------|--------|
| JD says "Python", resume says "Python" | ✅ catches it | ✅ catches it |
| JD says "ML", resume says "machine learning" | ✅ understands | ❌ misses (different string) |
| JD says "AWS S3", resume says "S3 bucket management" | ✅ understands | ❌ may miss |
| Resume stuffed with common words to game vectors | May be fooled | ✅ penalises common words |
| Very specific technical acronym (e.g. "CKA") | May not be in embedding | ✅ catches exact match |

Together they cover each other's blind spots.

---

## 6. Anomaly Detection — Isolation Forest

### 6.1 What Problem It Solves

Some resumes look suspicious:
- 15 years experience but only 2 skills listed (probably fake experience)
- Score is high but text is 50 words (keyword-stuffed)
- All scores are perfect maxima (could be gaming the system)

We want to flag these **without having labels** (we don't have a list of "bad" resumes). This is **unsupervised learning**.

### 6.2 Isolation Forest Algorithm

**Core Idea:** Anomalies are easier to isolate than normal points.

Imagine plotting all candidates on a 2D graph (score vs. text length). Normal candidates cluster together. An anomaly sits far from the cluster.

The algorithm:
1. Pick a random feature (e.g. score)
2. Pick a random split value within that feature's range
3. Recurse on each side until each point is isolated

**Normal point:** Takes many splits to isolate (surrounded by similar points, splits keep landing near other points).

**Anomaly:** Takes very few splits to isolate (it's alone in its region of the space).

```
Anomaly Score = average path length needed to isolate this point
Short path → anomaly
Long path  → normal
```

### 6.3 Implementation

```python
from sklearn.ensemble import IsolationForest

def detect_anomalies(candidates):
    # Features we use to detect anomalies
    features = []
    for c in candidates:
        features.append([
            c.get('score', 0),
            len(c.get('raw_text', '')),   # text length
            len(c.get('matched_skills', [])),  # skill count
        ])
    
    X = np.array(features)
    
    clf = IsolationForest(
        contamination=0.1,  # assume 10% of resumes might be anomalies
        random_state=42
    )
    predictions = clf.fit_predict(X)
    # -1 = anomaly, +1 = normal
    
    for i, c in enumerate(candidates):
        c['is_anomaly'] = (predictions[i] == -1)
    
    return candidates
```

**`contamination=0.1`** means "I expect about 10% of my data to be anomalies." This controls how strict the flagging is.

**Important:** The model fits fresh on every batch uploaded. It doesn't remember previous batches. An anomaly in batch A might not be anomalous in batch B if batch B has many similar candidates.

---

## 7. Label Encoders and Preprocessing

### 7.1 Why Categorical Encoding

Neural networks only understand numbers. `"IT"` and `"Finance"` are strings — they need to become numbers first.

**Label Encoding:**
```python
from sklearn.preprocessing import LabelEncoder

le = LabelEncoder()
le.fit(["Finance", "Human Resources", "IT", "Marketing", "Sales"])

le.transform(["IT"])       → [2]
le.transform(["Finance"])  → [0]
le.transform(["Sales"])    → [4]
```

This is stored in `label_encoders.pkl`. `pkl` = Python's pickle format — serialises a Python object to a file so you can load it later.

### 7.2 What Happens if the Department is Unknown?

If a resume says "Operations" which wasn't in training data, `le.transform(["Operations"])` throws an error. We handle this by mapping unknown values to `"Unknown"` (which IS in the encoder) before encoding:

```python
dept = info.get("department", "IT")
if dept not in le.classes_:
    dept = "Unknown"   # safe fallback
```

### 7.3 Why Not One-Hot Encoding?

One-Hot would turn "IT" into `[0, 0, 1, 0, 0]` (a vector with one 1). For 28 job roles that's 28 extra columns — sparse and wasteful. TabTransformer uses **embeddings** instead, which are *learned* dense vectors (32 numbers) that capture semantic similarity between categories.

---

## 8. The Full AI Scoring Pipeline (Code Walkthrough)

Here is the exact flow when a resume is uploaded, line by line:

```python
# 1. Parse the file
result = parse_resume(filepath)       # → {"raw_text": "...", "filename": "..."}
raw_text = result["raw_text"]

# 2. Extract features from text
info = extract_candidate_info(raw_text)
# info = {"name": "Arjun", "email": "...", "phone": "...",
#          "experience_years": 6, "education": "B.Tech IIT",
#          "department": "IT", "job_role": "Software Engineer"}

# 3. Get matched skills
matched_skills = get_matched_skills(raw_text)
# matched_skills = ["python", "docker", "kubernetes", ...]

# 4. Load the model (once at startup, cached)
ml_available = _load_models()  # loads tab_transformer.pth + label_encoders.pkl

# 5. TabTransformer score
tab_score = _get_tab_score(info)
# Internally: encode dept/role → embed → 2 transformer layers → 0-40

# 6a. If JD provided: real vector + TF-IDF
if job_description:
    resume_vec = _get_candidate_embedding(info)   # average word2vec of skills
    jd_vec     = _get_jd_embedding(jd)            # average word2vec of JD
    vec_score  = cosine_similarity(resume_vec, jd_vec) * 35

    tfidf_score = _get_tfidf_score(raw_text, jd)  # TfidfVectorizer → 0-25

# 6b. If no JD: profile richness proxy
else:
    composite   = compute_richness(info, matched_skills)  # 0-1
    vec_score   = composite * 35
    tfidf_score = composite * 25

# 7. Total
total_score = tab_score + vec_score + tfidf_score   # 0-100

# 8. Anomaly detection (run after full batch scored)
detect_anomalies(all_candidates)   # IsolationForest on [score, text_len, skills]

# 9. Save to MongoDB
save_to_mongodb(result)
```

---

## 9. AI Limitations and Honest Notes

### 9.1 TabTransformer Trained on IBM HR Data

The model was trained on the IBM HR Analytics Employee Attrition dataset — a public dataset of 1470 employees with their department, role, years of service, and attrition outcome. The "score" is derived from this attrition signal. 

This means: the model learned patterns from that specific company's data. It may not perfectly generalise to every industry. But it gives a meaningful signal about experience and role fit, which is what we need.

### 9.2 No JD = No Real Semantic Matching

When you upload without a JD, components 2 and 3 are estimates, not real AI scores. The TabTransformer still runs (that's always real). Vector similarity and TF-IDF only activate their full power with a JD.

### 9.3 Skills Matching is Keyword-Based

The skill extractor looks for words in a list of 302 known skills. If a resume uses "Typescript" and the list has "TypeScript" with different capitalisation — it might miss it. The list is case-insensitive, but domain-specific synonyms can be missed.

### 9.4 Anomaly Detection Has No Ground Truth

Isolation Forest is unsupervised — it has no labelled examples of "bad resumes." It flags statistical outliers. Some outliers are genuinely suspicious; others might just be unusually strong candidates. Always treat the ⚠️ flag as "worth reviewing" not "definitely bad."

---

## 10. AI Q&A — Professor Questions

**Q: What type of neural network is TabTransformer?**

A: It's a Transformer-based neural network adapted for tabular (structured) data. The architecture uses multi-head self-attention to learn interactions between categorical features (department, job role) after embedding them into dense vectors, combined with numerical features (experience, skills count). It has 2 Transformer layers with 4 attention heads each, and an embedding dimension of 32.

---

**Q: What is the attention mechanism and why is it important?**

A: Attention allows each input feature to "look at" all other features and decide how much to weight them. Standard neural networks process each input independently. The attention formula `softmax(QKᵀ/√d) × V` computes a weighted sum where weights are determined by how relevant each feature is to the current one. This lets the model learn that "Senior Engineer + 10 years" is a stronger signal than either alone.

---

**Q: What is backpropagation?**

A: Backpropagation is the algorithm used to train neural networks. After a forward pass produces a prediction, we compute the loss (how wrong the prediction was). Backpropagation uses the chain rule of calculus to compute the gradient of the loss with respect to every weight in the network — basically, how much each weight contributed to the error. The optimizer (Adam in our case) then adjusts all weights slightly in the direction that reduces the loss. Repeated millions of times, the model learns.

---

**Q: What is the difference between TF-IDF and word embeddings?**

A: TF-IDF is a sparse, frequency-based representation. Each word gets a score based on how often it appears in the document vs. the corpus. It cannot capture synonyms — "Python" and "py" are completely different to TF-IDF. Word embeddings are dense, learned vectors (e.g. 300 dimensions) where semantically similar words have similar vectors. "Python" and "Django" will be close in embedding space. TF-IDF is exact-match; embeddings capture meaning.

---

**Q: Why use three separate AI components instead of one model?**

A: Each component captures a different signal. TabTransformer captures structured profile strength (experience + role fit). Vector similarity captures semantic meaning when comparing to a job description. TF-IDF captures exact keyword relevance. A single model trained end-to-end would need a large labelled dataset of (resume, JD, quality score) triples — which we don't have. Combining three purpose-built components is more practical and each component is interpretable and debuggable independently.

---

**Q: What is unsupervised learning and how does Isolation Forest use it?**

A: Unsupervised learning finds patterns in data without labelled examples. Isolation Forest detects anomalies by randomly partitioning the feature space with splits. Normal points (surrounded by similar points) require many splits to isolate. Anomalies (outliers) are isolated in very few splits because they're far from the main cluster. The algorithm returns an anomaly score equal to the average path length — short path means anomaly. We use it because we have no labelled dataset of "fraudulent resumes."

---

**Q: How does the system handle a resume with a job role not seen during training?**

A: We check if the extracted job role exists in the LabelEncoder's known classes. If it doesn't (e.g., "Astronaut"), we map it to `"Unknown"` — which IS a class in the encoder (we deliberately included it during training). The embedding for "Unknown" was learned just like any other class, so the model still produces a valid output rather than crashing.

---

**Q: What is the curse of dimensionality and does it affect this project?**

A: The curse of dimensionality means that as the number of features grows, data becomes increasingly sparse and distance metrics become less meaningful. In HireFlow, we mitigate this by: (1) using only 4 features for the TabTransformer — keeping the input space small; (2) using embeddings that compress high-cardinality categories into 32 dimensions; (3) using TF-IDF with `max_features=5000` to cap the vocabulary size. The risk is highest in the vector similarity component where we use 300-dimension word vectors, but cosine similarity is less affected by high dimensions than Euclidean distance.

---

**Q: How would you improve this AI system?**

A: Several improvements are possible: (1) Fine-tune a BERT model on resume-JD pairs for better semantic similarity — current implementation uses simple word2vec averaging. (2) Train the TabTransformer on a larger, domain-specific dataset rather than the IBM HR dataset. (3) Add a feedback loop — let HR managers mark candidates as hired/rejected, and retrain the model on that signal periodically. (4) Use a Named Entity Recognition (NER) model to extract skills and education more accurately instead of regex patterns. (5) Implement Explainable AI (SHAP values) to show why each candidate got their specific score.

---

## 11. Summary — AI Techniques Used

| Technique | Category | Used for |
|-----------|---------|---------|
| TabTransformer | Deep Learning (Supervised) | Score candidate from structured features |
| Multi-head Self-Attention | Transformer Architecture | Learn feature interactions |
| Embeddings (LabelEncoder → learned) | Representation Learning | Encode categorical features |
| Word2Vec / Word Embeddings | NLP | Convert text to semantic vectors |
| Cosine Similarity | Linear Algebra | Measure semantic closeness |
| TF-IDF | Classical NLP / Information Retrieval | Measure keyword relevance |
| Isolation Forest | Unsupervised Anomaly Detection | Flag suspicious resumes |
| Regex (NLP preprocessing) | Rule-based NLP | Extract name, email, phone, skills |
| Label Encoding | Preprocessing | Convert categories to integers |
| Pickle serialisation | Model Persistence | Save/load trained model objects |

---

*This document focuses entirely on the AI components of HireFlow. For Big Data (Spark, HDFS, DAGs) refer to PROJECT_GUIDE.md.*
