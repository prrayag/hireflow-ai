# Neural ranking training

This pipeline converts the synthetic 100-resume archive into 500 resume–JD
pairs across five job descriptions, fine-tunes the cross-encoder, and evaluates
ranking and basic name-masking stability.

The generated labels are **weak synthetic labels based on skill coverage**.
They are suitable for testing the training machinery, but must not be reported
as recruiter-validated model accuracy.

```bash
backend/venv/bin/python backend/training/prepare_dataset.py
backend/venv/bin/python backend/training/evaluate.py \
  --fine-tuned /tmp/model-that-does-not-exist
backend/venv/bin/python backend/training/train_cross_encoder.py
backend/venv/bin/python backend/training/evaluate.py
```

For a credible model, replace the weak labels with independent human relevance
judgements while preserving the resume-level train/validation/test split.

# NER skill extraction (deep-learning resume parser)

Two sequence-labelling models tag each word of a resume as `TECH` (tools,
languages, frameworks) or `SOFT` (abilities) in BIO format. Both are trained on
**SkillSpan** (Zhang, Jensen, Sonniks and Plank, NAACL 2022, CC BY 4.0):
human-annotated sentences from 263 English job postings, with the official
train/dev/test split by document.

| Model | What it shows | Script |
|---|---|---|
| BiLSTM-CRF (word embeddings + character CNN), written from scratch | Architecture design, CRF loss (forward algorithm) and Viterbi decoding | `train_ner_bilstm_crf.py` |
| DistilBERT fine-tuned for token classification | Transfer learning from a pretrained transformer | `train_ner_transformer.py` |

```bash
backend/venv/bin/python backend/training/ner_data.py               # download SkillSpan
backend/venv/bin/python backend/training/train_ner_bilstm_crf.py   # ~5-10 min on CPU
backend/venv/bin/python backend/training/train_ner_transformer.py  # ~20 min on Apple MPS
backend/venv/bin/python backend/training/evaluate_ner.py           # dictionary vs BiLSTM-CRF vs DistilBERT
```

Outputs: `backend/model_artifacts/ner_bilstm_crf_v1/`,
`backend/model_artifacts/ner_distilbert_v1/` (its `model.safetensors` is
git-ignored because it is ~260 MB) and `results/ner_evaluation.{json,md}`.

At runtime `backend/ner_parser.py` uses DistilBERT when its weights exist,
otherwise the BiLSTM-CRF, otherwise the keyword dictionary. Model skills are
added to dictionary matches (never replace them). Set `NER_BACKEND` to
`distilbert`, `bilstm_crf` or `off` to force a choice.

# Human ranking benchmark

The cross-encoder results above use synthetic labels. This benchmark replaces
them with human judgements (10 resumes x 3 job descriptions = 30 pairs).

```bash
backend/venv/bin/python backend/training/human_benchmark.py prepare    # already done; sheet is committed
# Two people independently fill annotator_1 / annotator_2 (0-3) in
# backend/training/human_benchmark/labels.csv using GUIDE.md
backend/venv/bin/python backend/training/human_benchmark.py evaluate
```

`evaluate` reports agreement (quadratic-weighted Cohen's kappa), then
Precision@3, Recall@5, NDCG@5, MRR and Spearman correlation for the full
system, bi-encoder only, cross-encoder only and skill coverage only, both with
NER skill extraction and with the dictionary only.
