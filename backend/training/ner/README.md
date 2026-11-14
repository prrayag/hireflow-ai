# Neural resume parser (NER): how it works and how it was evaluated

## What it is
`backend/ner_parser.py` runs a pretrained DistilBERT token-classification model
(`oksomu/resume-ner`, Apache-2.0, **not trained by us**) over a resume and reads off
NAME, DEGREE, TITLE, COMPANY, DATE and SKILL spans. Email and phone stay on regex.
`app.py` calls it first and falls back to `regex_parser.extract_metadata` if the model
is missing, fails, or is under 0.70 average confidence.

Switches: `PARSER_MODE=auto|ner|regex`, `NER_MODEL=<hub id or path>`, `FREE_TEXT_SKILLS=true|false`; speed switches are listed under Speed.

## What it changes in the app
- Candidate name comes from the resume text instead of the file name.
- Degree levels include PhD and recognise B.S., BCA, MBA, PGDM and similar.
- Experience reads "seven years" written in words, and ignores school dates when
  it falls back to a career span.
- New fields: `titles`, `companies`, `extra_skills`, `parser_mode`, `confidence`.

## What it does not change
- **Only 15 of the 100 final-score points depend on the parser** (10 skill coverage,
  5 experience match). The bi-encoder and cross-encoder read the resume text.

## Free-text skill matching (`skill_matcher.py`, `dl_pipeline.extract_jd_phrases`)
The 50-skill dictionary gave every non-IT resume a skill coverage of 0. Now:
1. A small **rule-based** extractor reads requirement lists from the job description
   ("Required: ...", "Skills: ...", "Responsibilities include ...") into phrases such as
   "wound care". The NER model is not used on the JD: it found no skills in non-IT job
   descriptions (it was trained on resumes).
2. Each phrase is matched to the candidate's skills (dictionary skills plus NER
   `extra_skills`) by exact or contained words, then by Sentence-BERT cosine similarity
   (default 0.75, `SKILL_MATCH_THRESHOLD`). It reuses the bi-encoder already loaded.
3. Coverage = matched / (dictionary skills + phrases). The weights are unchanged.

`FREE_TEXT_SKILLS=false` restores dictionary-only coverage. The deterministic fallback in
`app.py` (used only if the whole search fails) still uses the dictionary only.

Sanity check, `skill_gap_eval.py` (5 JDs written by the author for roles in the 10 image
resumes, so only a check, not an accuracy figure):

| | target resume first alone | coverage, target | coverage, other resumes |
|---|---|---|---|
| dictionary only | 1 of 5 | 20% | 0% |
| free-text, threshold 0.75 | 4 of 5 | 67% | 2% |

Thresholds 0.6 to 0.9 gave the same 4 of 5. The miss is limited by NER recall: it found
2 of the photo editor's 5 skills. JDs with no requirements list give no phrases and fall
back to dictionary skills only.

## Speed (measured on this machine, 16 logical CPUs, no GPU)
Where the time went, for a 10-resume upload: first request after a restart about 17 s,
later requests about 2.5 s. The difference is model loading (NER about 7 s, Sentence-BERT
about 5 s, OCR reader about 5 s). Changes:

| Change | Why | Env switch |
|---|---|---|
| Models are loaded in the background when the server starts (`warm_up()`, about 10 s) | the first upload is no longer the slow one | `WARMUP=false` |
| Spark is used only from 1000 resumes (was 8) | 100 resumes: 2.2 s in plain Python, 9.4 s with Spark; the chunking is too light to repay the job start-up and serialisation | `SPARK_MIN_RESUMES=8` brings Spark back for a demo |
| OCR results cached by file hash; 3 or more new images are OCR'd in parallel worker processes (`ocr_service.py`) | EasyOCR needs about 15 s per image on CPU | `OCR_WORKERS`, `OCR_PARALLEL_MIN` |
| Parse results cached by resume text | a re-uploaded resume is not parsed again | none |

Real `/api/upload` with MongoDB, one run each:

| Upload | Before | After |
|---|---|---|
| 100 DOCX resumes in a ZIP | 38 s | 17 to 19 s |
| The same ZIP again | 38 s | 6 s |
| 4 image resumes | 67 s | 44 s |
| The same 4 images again | 67 s | under 1 s |

What did not work, and why it is not used: bigger OCR batch size or smaller canvas (no
change in time); batched NER calls (slower, because padding of uneven chunks); 8-bit
quantised NER (1.27x faster but it changed the extracted entities in all 110 test
resumes). OCR of a single new image is still about 15 s and cannot be fixed with settings:
the options are a GPU or a different OCR engine such as Tesseract or an ONNX one, which are
not installed here.

About Hadoop: the code never used HDFS or YARN. The only distributed part is the Spark
`flatMap` that splits resumes into chunks, and `PROJECT_GUIDE.md` describes HDFS as
background. A Hadoop file system would not make this faster: the cost is model inference on one
machine, not reading files.

## Gold set (`gold/`)
| Group | Count | Labels | Use |
|---|---|---|---|
| images (`1`-`10`) | 10 | hand transcription plus draft labels, **to be reviewed by a person** | varied layouts; tested on clean text, not OCR |
| template (`firstname_lastname_N`) | 100 | read from the file text by `fill_docx_gold.py` | pipeline check only, one template |
| kaggle (`kg_*`) | 40 | draft labels for degree, experience and job titles, **to be reviewed by a person**. Skills and companies are not labelled (keyword-dump skill sections, employers masked as "Company Name"). Name is labelled for 1 resume only, the rest have no name. | the main held-out test |

Labelling rules: [LABELING.md](LABELING.md). Model and dataset choices and licences:
[DATASETS.md](DATASETS.md).

## Reproduce
```
cd backend
python training/ner/fill_docx_gold.py
python training/ner/evaluate_parsers.py --group images      # or template, kaggle, all
python training/ner/ranking_impact.py --group images
python -m unittest tests.test_ner_parser
```
Results are written to `training/results/ner_evaluation.json` and
`training/results/ranking_impact_<group>.json`.

## Results so far (not final)
| | images: regex | images: NER | template: regex | template: NER |
|---|---|---|---|---|
| name accuracy | 0% | 100% | 100% | 100% |
| degree accuracy | 70% | 100% | 0% | 100% |
| experience within 1 year | 60% | 100% | n/a | n/a |
| skills as written, F1 | 0% | 61% | 85% | 96% |
| job titles, F1 | 0% | 70% | 0% | 99% |
| companies, F1 | 0% | 65% | 0% | 100% |
| canonical skills, F1 | 50% | 50% | 99% | 99% |

Kaggle set (40 resumes, draft labels; the number of resumes scored differs by field):

| | regex | NER |
|---|---|---|
| degree accuracy (n=40) | 42.5% | 80% |
| experience within 1 year (n=16) | 56% | 81% |
| experience mean error (n=16) | 5.3 years | 1.4 years |
| job titles F1 (n=40) | 0% | 71% |
| name accuracy (n=1) | 0% | 100% |

Ranking impact on the 15 parser-dependent points (error vs the gold labels, mean over
8 job descriptions): images regex 0.43, NER 0.00; template regex 0.07, NER 0.07;
Kaggle (16 resumes with an experience label) regex 1.06, NER 0.31, with rank agreement
against the gold ordering of 0.36 (regex) and 0.72 (NER).

## Limits that must be stated with these numbers
1. The 10 image resumes were used while fixing parser bugs, and their labels are
   drafts. Treat them as an upper bound.
2. The template set is a single layout. It shows the pipeline works, not that the
   model generalises.
3. `oksomu/resume-ner` reports training on Kaggle resumes, probably the same dataset
   as `gold/kg_*`. The Kaggle scores above may be inflated for that reason.
7. All draft labels (images and Kaggle) were written by the assistant from the resume
   text, not from any parser output. They have not been checked by a second person, so
   no inter-annotator agreement is reported. Several Kaggle experience figures come from
   the span of closed date ranges and are marked in each file's `notes`.
8. The Kaggle experience result uses only the 16 resumes that state their experience or
   have only closed date ranges. "Current" in a resume depends on when it was written,
   so those were left unlabelled.
4. Regex scores 0% on titles, companies and name because it has no such field, not
   because it fails at them.
5. The regex parser's name comes from the file name, so the name comparison is
   "text-based name vs file name".
6. Known NER failures: all-caps layouts (the nanny resume), truncated company names,
   stray spans such as "Certificates" as a skill.
