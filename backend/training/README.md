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
