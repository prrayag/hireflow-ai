# HireFlow AI: Previous System vs Trained Deep-Learning System

## 1. Purpose of this document

This document records how HireFlow AI changed from an embedding-similarity
prototype into a two-stage neural ranking system. It explains the architecture,
dataset creation, training process, evaluation metrics, fairness test, runtime
behaviour, and important limitations.

The current system uses a trained neural network. More precisely, it uses a
pretrained Sentence-BERT model for retrieval and a MiniLM cross-encoder that we
fine-tuned using weakly supervised resume–job-description pairs.

---

## 2. Previous version

### 2.1 Previous processing pipeline

The earlier application followed this approximate pipeline:

```text
Resume document
    ↓
PDF/DOCX/image text extraction
    ↓
Split text after every 20 words
    ↓
Sentence-BERT embedding for every chunk
    ↓
Cosine similarity between each chunk and the full JD
    ↓
Use the candidate's best matching chunk
    ↓
70% semantic similarity + 30% general experience score
    ↓
Artificially map the result into the 55–95 range
```

### 2.2 What the previous system did well

- It used a real pretrained transformer (`all-MiniLM-L6-v2`).
- It could match semantically related text, not only exact keywords.
- It supported PDF, DOCX, image and ZIP uploads.
- It stored embedding vectors for vector search.
- It had a Python fallback when MongoDB was unavailable.

### 2.3 Limitations of the previous system

#### Arbitrary chunks

The resume was split after every 20 words. A sentence or employment entry could
be cut in half, causing the model to lose context.

#### Best-chunk bias

One highly similar sentence could determine a candidate's ranking even if the
rest of the resume was unrelated.

#### No joint JD–resume reasoning

Sentence-BERT encoded the JD and resume chunk independently. Cosine similarity
could compare their vectors, but the model could not directly attend from an
individual JD requirement to evidence inside the resume.

#### Experience was not requirement-aware

More experience always increased the result even when the JD did not require
that amount of experience.

#### Artificial score inflation

The final score was compressed into approximately 55–95%. Consequently, an
irrelevant candidate could still appear to be a moderate match.

#### Limited explanations

The API returned a combined score but did not return matched skills, missing
skills, component scores, model version, or supporting resume evidence.

#### Misleading terminology

The UI called the model “JobBERT,” but the actual model was the general-purpose
`sentence-transformers/all-MiniLM-L6-v2` model.

#### No model training in the current branch

The earlier running branch used pretrained inference. Documentation mentioned a
TabTransformer, but its implementation and model artifacts were absent from the
active code.

---

## 3. Current version

### 3.1 Current neural-ranking pipeline

```text
Resume document
    ↓
Text extraction
    ↓
Section detection: Summary, Experience, Skills, Projects, Education
    ↓
Sentence-aware chunks of up to approximately 90 words
    ↓
Sentence-BERT bi-encoder retrieval
    ↓
Aggregate the candidate's three strongest evidence chunks
    ↓
Fine-tuned MiniLM cross-encoder reranking
    ↓
Skill-gap analysis + JD-relative experience match
    ↓
Transparent final score from 0–100
    ↓
Score components, matched/missing skills and evidence returned to the UI
```

### 3.2 Current score composition

When both neural models are available:

```text
Final score = 45% bi-encoder semantic score
            + 40% cross-encoder relevance score
            + 10% skill coverage
            +  5% experience requirement match
```

If the cross-encoder is unavailable:

```text
Fallback score = 80% bi-encoder semantic score
               + 15% skill coverage
               +  5% experience requirement match
```

Scores are clipped to the honest `0–100` range. They are no longer forced into
the 55–95 range.

### 3.3 New API explanation fields

Each ranked candidate can now include:

```json
{
  "ai_score": 84.78,
  "semantic_score": 77.60,
  "reranker_score": 95.20,
  "skill_coverage": 100.0,
  "experience_match": 100.0,
  "matched_skills": ["Python", "AWS"],
  "missing_skills": ["Kubernetes"],
  "relevant_sentences": ["Evidence selected from the resume..."],
  "inference_mode": "bi-encoder+cross-encoder",
  "model_version": "hireflow-weakly-supervised-ranker-v1"
}
```

---

## 4. Before-and-after comparison

| Area | Previous version | Current version |
|---|---|---|
| Chunking | Fixed 20-word blocks | Section-aware, sentence-boundary chunks |
| Retrieval | Sentence-BERT cosine similarity | Batched Sentence-BERT bi-encoder retrieval |
| Candidate evidence | Single best chunk | Weighted aggregation of top three chunks |
| Neural reranking | None | Fine-tuned MiniLM cross-encoder |
| Custom training | None in the running branch | Two-epoch cross-encoder fine-tuning |
| Skill handling | Mostly exact fixed keywords | Canonical aliases such as `k8s → Kubernetes` |
| Skill explanation | Candidate skill list only | Matched skills, missing skills and coverage |
| Experience | General seniority bonus | Compared against years required by the JD |
| Score scale | Artificially mapped to 55–95 | Transparent 0–100 score |
| Candidate grouping | Name-based in ranking stage | Stable `resume_id` grouping |
| Evidence | Not returned | Top relevant resume passages returned |
| Model identity | Labelled “JobBERT” inaccurately | Model and inference mode reported explicitly |
| Large batches | Spark worker import failure | Spark module shipping plus safe local fallback |
| Tested scale | Small batches | Verified with 10 mixed files and 100 DOCX resumes |
| Evaluation | No ranking benchmark | Precision@3, Recall@5, NDCG@5, MRR, correlation |
| Fairness check | None | Candidate-name masking stability test |

---

## 5. Deep-learning concepts used

### 5.1 Transformer neural network

A transformer is a neural-network architecture based on attention. Attention
allows the model to assign different importance to words depending on their
context. For example, “Python” near “data pipeline” has a different context from
“python” used as an unrelated word.

Both current text models are based on the transformer architecture.

### 5.2 Tokens and tokenization

Before text enters a transformer, a tokenizer divides it into tokens. A token
may be a complete word, part of a word, punctuation, or a special marker.

For the cross-encoder, the logical input is:

```text
[CLS] Job description [SEP] Resume evidence [SEP]
```

The implementation limits the combined input to 384 tokens during training to
control CPU time and memory usage.

### 5.3 Embeddings

An embedding is a dense numeric vector that represents semantic information.
The Sentence-BERT model produces a 384-dimensional vector for each text chunk.
Texts with similar meanings should have vectors pointing in similar directions.

### 5.4 Bi-encoder

A bi-encoder processes the JD and resume text independently:

```text
JD → Transformer → JD vector
Resume chunk → Transformer → Resume vector
```

Advantages:

- Resume embeddings can be calculated once and stored.
- Many candidates can be compared quickly.
- Vector search can scale to large candidate collections.

Limitation:

- Because the texts are encoded separately, the model cannot perform detailed
  token-to-token reasoning between a specific requirement and resume evidence.

HireFlow uses `sentence-transformers/all-MiniLM-L6-v2` as its bi-encoder.

### 5.5 Cosine similarity

Cosine similarity measures the angle between two embedding vectors:

```text
cosine_similarity(A, B) = (A · B) / (||A|| × ||B||)
```

The closer the vectors point in the same direction, the greater their semantic
similarity. Cosine similarity is a mathematical comparison, not itself a neural
network.

### 5.6 Cross-encoder

A cross-encoder receives the JD and resume evidence together. Self-attention can
connect words in the JD directly to words in the resume.

```text
JD + resume evidence
        ↓
Single transformer
        ↓
One relevance logit
```

This is slower than a bi-encoder because every JD–candidate pair requires a new
forward pass. Therefore, HireFlow uses a two-stage design:

1. The fast bi-encoder retrieves likely candidates.
2. The more accurate cross-encoder reranks only those candidates.

The base cross-encoder is `cross-encoder/ms-marco-MiniLM-L-6-v2`.

### 5.7 Logit and sigmoid

The final neural layer produces a raw value called a logit. A sigmoid converts
that unrestricted value into a value between zero and one:

```text
sigmoid(x) = 1 / (1 + e^(-x))
```

HireFlow converts the result to a percentage for its reranker component.

### 5.8 Transfer learning

Training a transformer from random weights would require a very large dataset
and substantial compute. Instead, HireFlow uses transfer learning:

1. Start with MiniLM weights learned from a large external text corpus.
2. Continue training those weights on resume–JD relevance pairs.
3. Save the updated weights as the HireFlow checkpoint.

This process is called fine-tuning.

### 5.9 Weak supervision

The current 100 resumes did not contain recruiter relevance labels. To exercise
the complete training pipeline, the system generated labels using explicit skill
coverage rules.

Each resume was paired with five job descriptions. Skill coverage was converted
into four relevance levels:

- `0`: irrelevant
- `1`: weak match
- `2`: good match
- `3`: excellent match

This is called weak supervision because labels come from a heuristic rather than
independent human judgement.

Weak supervision is useful for:

- Proving that the training code works.
- Testing data loading, backpropagation and model saving.
- Teaching the model the terminology used in the synthetic dataset.

It does not prove real-world hiring accuracy.

### 5.10 Train, validation and test splits

The generated dataset contains:

```text
100 unique resumes
5 job descriptions
500 resume–JD pairs
```

The split is performed by resume identity:

```text
Training:   70 resumes = 350 pairs
Validation: 15 resumes =  75 pairs
Test:       15 resumes =  75 pairs
```

Resume-level splitting prevents the same candidate text from appearing in both
training and test data. Without this precaution, the model could memorize a
resume and produce misleadingly high test metrics. This problem is called data
leakage.

### 5.11 Label distribution

The 500 generated pairs contain:

```text
Label 0 — irrelevant: 124
Label 1 — weak:       201
Label 2 — good:       131
Label 3 — excellent:   44
```

The thresholds were selected so every test job had relevant and irrelevant
candidates. An earlier, more restrictive threshold produced an excessively
imbalanced dataset and was corrected before training.

### 5.12 Soft relevance targets

The four relevance labels are normalized before training:

```text
0 → 0.000
1 → 0.333
2 → 0.667
3 → 1.000
```

This preserves the ordered nature of the labels instead of treating “weak” and
“good” as unrelated categories.

### 5.13 Binary cross-entropy with logits

The training objective is `BCEWithLogitsLoss`. It combines a sigmoid operation
with binary cross-entropy in a numerically stable implementation.

For a soft target `y` and logit `x`, the loss penalizes disagreement between the
predicted relevance and target relevance. Lower loss indicates closer agreement
with the training or validation targets.

### 5.14 Forward pass

During a forward pass:

1. The tokenizer converts a JD–resume pair into tensors.
2. Tensors pass through MiniLM transformer layers.
3. Attention produces contextual representations.
4. The final classification layer produces a relevance logit.
5. The loss compares the logit with the normalized target.

### 5.15 Backpropagation

Backpropagation calculates how much each trainable weight contributed to the
loss. PyTorch stores these derivatives as gradients.

```python
loss.backward()
```

The gradients point toward changes that should reduce future loss.

### 5.16 AdamW optimizer

AdamW updates model weights using adaptive learning rates and decoupled weight
decay. The training configuration uses a learning rate of `2e-5`, a common
starting value for transformer fine-tuning.

```python
optimizer = AdamW(model.parameters(), lr=2e-5)
```

### 5.17 Mini-batches

The training data is processed in batches of eight JD–resume pairs. Mini-batches
make training more memory-efficient and provide more frequent weight updates
than processing the entire dataset at once.

### 5.18 Epoch

One epoch is one complete pass through the training split. The model was trained
for two epochs:

| Epoch | Training loss | Validation loss |
|---:|---:|---:|
| 1 | 0.6203 | 0.5037 |
| 2 | 0.5232 | 0.4462 |

Both training and validation loss decreased. This indicates that the model
learned the weak-label task without an immediate sign of validation degradation.

### 5.19 Gradient clipping

Gradient norms are clipped to `1.0`. This limits unusually large gradients that
could make transformer training unstable.

### 5.20 Checkpointing

After every epoch, validation loss is measured. The model is saved only when
validation loss improves. The resulting local checkpoint is:

```text
backend/model_artifacts/cross_encoder_v1/
```

Its model version in API results is:

```text
hireflow-weakly-supervised-ranker-v1
```

If the checkpoint is absent, the application safely falls back to the pretrained
cross-encoder.

---

## 6. Evaluation concepts and results

### 6.1 Precision@3

Precision@3 measures how many of the top three results are relevant:

```text
relevant candidates in top 3 / 3
```

This reflects the first candidates a recruiter is likely to inspect.

### 6.2 Recall@5

Recall@5 measures how many relevant candidates were recovered in the top five:

```text
relevant candidates in top 5 / all relevant candidates
```

### 6.3 NDCG@5

Normalized Discounted Cumulative Gain considers both relevance level and ranking
position. Placing an excellent candidate first is rewarded more than placing the
same candidate fifth.

### 6.4 Mean Reciprocal Rank

MRR measures how early the first relevant candidate appears. A relevant result
at rank one gives a reciprocal rank of `1.0`; rank two gives `0.5`.

### 6.5 Spearman correlation

Spearman correlation measures whether higher model scores generally correspond
to higher relevance labels, without requiring a perfectly linear relationship.

### 6.6 Held-out synthetic results

| Method | Precision@3 | Recall@5 | NDCG@5 | MRR |
|---|---:|---:|---:|---:|
| Skill-rule baseline | 1.0000 | 0.9000 | 1.0000 | 1.0000 |
| Sentence-BERT bi-encoder | 0.6667 | 0.6067 | 0.7710 | 1.0000 |
| Pretrained cross-encoder | 0.8667 | 0.7533 | 0.8818 | 1.0000 |
| Fine-tuned cross-encoder | 1.0000 | 0.9000 | 1.0000 | 1.0000 |

Fine-tuned cross-encoder correlation with weak labels: `0.9397`.

The skill-rule baseline is perfect by construction because the same skill rule
created the labels. It must not be interpreted as an independent accuracy
result. The useful observation is that fine-tuning taught the neural model to
approximate the synthetic rule on unseen resumes.

---

## 7. Fairness stability check

The evaluation replaces each candidate's displayed name with “Candidate Name”
without changing their qualifications, then measures the score difference.

| Model | Mean absolute change | Maximum absolute change |
|---|---:|---:|
| Pretrained cross-encoder | 1.5401 points | 7.0905 points |
| Fine-tuned cross-encoder | 1.3358 points | 4.5543 points |

The fine-tuned model was more stable in this test. However, name masking is only
a basic counterfactual test. It does not establish that the system is free from
bias across gender, ethnicity, age, disability, education, location, or other
protected and socioeconomic attributes.

---

## 8. Large-batch improvements

The original Spark path failed for batches of eight or more resumes because
worker processes could not import the `processor` module.

The new design moves Spark-safe preprocessing into the dependency-light
`dl_pipeline.py` module and explicitly ships that module to Spark workers. If a
Spark job still fails, processing automatically falls back to the local Python
path instead of returning an HTTP 500 error.

Verified results:

```text
Mixed batch: 10 PDF/DOCX/PNG/JPG resumes → 35 chunks → HTTP 200
Large batch: 100 DOCX resumes → 520 chunks → HTTP 200
```

---

## 9. Important limitations

### Synthetic labels are not recruiter labels

Current evaluation measures agreement with a skill-overlap heuristic. It does
not measure actual hiring success, job performance, or recruiter preference.

### Synthetic resumes are structurally repetitive

The 100 resumes share a common template and similar experience text. Real
resumes contain much greater variation, ambiguity, missing data and formatting
noise.

### The model artifact is local

The fine-tuned checkpoint is approximately 88 MB and is intentionally excluded
from normal Git commits. Another machine will use the pretrained fallback unless
the artifact is transferred, downloaded from model storage, or regenerated by
running the training script.

### Scores are ranking aids, not hiring decisions

The model should help a human review candidates. It should not automatically
reject applicants or infer protected characteristics.

### Skill rules still influence the final score

The final ranking is hybrid. It combines neural scores with explicit skill and
experience signals. This improves transparency but means the final number is not
a pure neural probability.

---

## 10. Reproducing the work

Generate the weak-label dataset:

```bash
backend/venv/bin/python backend/training/prepare_dataset.py
```

Record a pretrained baseline:

```bash
backend/venv/bin/python backend/training/evaluate.py \
  --fine-tuned /tmp/model-that-does-not-exist \
  --output backend/training/results/baseline.json
```

Fine-tune the cross-encoder:

```bash
backend/venv/bin/python backend/training/train_cross_encoder.py \
  --epochs 2 \
  --batch-size 8
```

Evaluate the fine-tuned model:

```bash
backend/venv/bin/python backend/training/evaluate.py
```

Run automated tests:

```bash
backend/venv/bin/python -m unittest discover -s backend/tests -v
```

---

## 11. Relevant implementation files

| File | Responsibility |
|---|---|
| `backend/app.py` | Upload API, document parsing and response construction |
| `backend/dl_pipeline.py` | Section chunking, skill normalization and structured signals |
| `backend/processor.py` | Bi-encoder retrieval, cross-encoder reranking and final scoring |
| `backend/training/prepare_dataset.py` | Weak-label dataset generation and resume-level splitting |
| `backend/training/train_cross_encoder.py` | PyTorch fine-tuning and checkpoint selection |
| `backend/training/evaluate.py` | Ranking metrics and name-masking stability evaluation |
| `backend/training/common.py` | Job profiles, label rules and metric utilities |
| `backend/training/data/metadata.json` | Dataset provenance, split and label distribution |
| `backend/training/results/evaluation.json` | Recorded held-out results |
| `backend/tests/test_dl_pipeline.py` | Preprocessing and feature tests |
| `backend/tests/test_training_pipeline.py` | Split, label and metric tests |
| `frontend/src/pages/DashboardPage.jsx` | Neural score and evidence presentation |

---

## 12. Correct project claim

An accurate description is:

> HireFlow AI uses a two-stage neural ranking architecture. A Sentence-BERT
> bi-encoder retrieves semantically relevant resume evidence, and a MiniLM
> cross-encoder fine-tuned with weak supervision reranks candidates against a job
> description. The hybrid score also includes explicit skill coverage and
> requirement-aware experience signals. The current benchmark uses synthetic
> labels and must be followed by human-labelled evaluation before making
> real-world accuracy claims.

The next research step is to collect independent labels from multiple human
reviewers, measure reviewer agreement, retrain on those labels, and compare the
human-trained model against all current baselines.
