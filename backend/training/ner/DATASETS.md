# Resume NER: model and dataset decisions (Phase 0)

Checked on 2026-11-14 from the Hugging Face model and dataset cards. Licences and
metrics below are what the authors state; none of the metrics have been
reproduced by us.

## Candidate pretrained models

| Model | Base | Licence | Labels | Author-reported F1 | Notes |
|---|---|---|---|---|---|
| [oksomu/resume-ner](https://hf.co/oksomu/resume-ner) | DistilBERT-cased (65M) | Apache-2.0 | NAME, EMAIL, PHONE, LOCATION, COMPANY, TITLE, DATE, DEGREE, INSTITUTION, FIELD, SKILL, CERT, LANGUAGE | 97.8% entity F1 overall, 69.2% on noisy OCR text | Smaller and faster. **Trained partly on Kaggle resumes (2,483 with Gemini "silver" labels).** Our resumes also come from Kaggle, so overlap is possible. |
| [yashpwr/resume-ner-bert-v2](https://hf.co/yashpwr/resume-ner-bert-v2) | BERT-base-cased (108M) | Apache-2.0 | Name, Email Address, Phone, Location, Companies worked at, Designation, Skills, Years of Experience, Degree, College Name, Graduation Year, UNKNOWN | 90.9% F1 | Has a "Years of Experience" label. Trained on DataTurks and other data. 431 MB. README examples truncate at 128 tokens. |
| [dslim/bert-base-NER](https://hf.co/dslim/bert-base-NER) | BERT-base-cased | MIT | PER, ORG, LOC, MISC (CoNLL-2003) | n/a for resumes | General news NER. Fallback for names only. No skills. |

## Candidate training data (only needed for Phase 5 fine-tuning)

| Dataset | Licence | Size | Notes |
|---|---|---|---|
| [yashpwr/resume-ner-training-data](https://hf.co/datasets/yashpwr/resume-ner-training-data) | MIT | 22.9K rows | Chat-message format, needs conversion to BIO. Provenance unclear. |
| DataTurks "Resume Entities for NER" (Kaggle) | Check the Kaggle page before use | about 200 resumes | Small, public, widely used. Licence not verified yet. |
| AuraATS synthetic 12K (sanaullah7964) | No licence shown | 12K | Fully synthetic. Not useful for proving real-world quality. |

## Decision

1. **Primary model: `oksomu/resume-ner`.** It has the labels we need (NAME, SKILL,
   DEGREE, COMPANY, TITLE, DATE), it is small, and the licence allows use.
2. **Comparison model: `yashpwr/resume-ner-bert-v2`.** Run both on the gold set
   and keep the better one. The v2 model has a direct "Years of Experience" label.
3. **Do not fine-tune until the gold-set results show a gap.** Phase 5 stays optional.
4. **Leakage risk to handle in Phase 1.** `oksomu/resume-ner` saw Kaggle resumes
   during training. Our gold resumes are also from Kaggle. Before trusting the NER
   score, find out which Kaggle dataset the team used and compare it with the
   dataset the model card names. Report any overlap, or evaluate on resumes
   outside that dataset. Otherwise the NER result may be inflated.
5. **Licences:** all three models allow use with attribution. Cite the models in
   the README and the report.

## Open items
- Confirm which Kaggle resume dataset the team's 50+ resumes came from, and its licence.
- Verify the DataTurks licence if we go to Phase 5.
- Test both models on a few of our resumes to see label quality before committing.
