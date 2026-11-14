# Gold-set labelling guide

Each resume has `gold/<id>.txt` (the text the parsers see) and `gold/<id>.json`
(your labels). Label from the resume itself, not from any parser's output.

| Field | Rule |
|---|---|
| `name` | The candidate's full name as written at the top of the resume. |
| `skills` | Every skill the resume states, written as it appears. The evaluator canonicalises them afterwards, so do not rename `k8s` yourself. Include skills listed under a Skills heading and tools named in job bullets. Skip soft-skill filler ("hard-working"). |
| `degree` | Highest degree: `"Bachelor's Degree"`, `"Master's Degree"`, `"PhD"`, `"Diploma"`, or `"Not Found"`. Same vocabulary as the regex parser, so the two can be compared. |
| `experience_years` | Total professional experience in whole years. Use the stated figure ("11 years") if the resume gives one, else latest end year minus earliest start year of jobs. `0` for students with no jobs. Internships count only if there is nothing else. |
| `job_titles` | Titles held, one entry per position. |
| `companies` | Employers only, not universities. |
| `notes` | Anything ambiguous. Two-column layouts and ambiguous dates go here. |

## Kaggle resumes (`gold/kg_*.json`)
The names were removed from this dataset, so leave `name` as `""` and the evaluator
will skip it. Employers are often masked as "Company Name": leave `companies` empty
when no real name is given. List unique employers only in `companies`.

## Rules
- Fill `labeller` with your initials. A second person labels about 10 resumes
  without looking at the first labels, so we can report agreement.
- Fix OCR errors in the `.txt` only if you are testing the parsers on clean text.
  Record which you did in `notes`. Never edit a `.txt` after you start labelling.
- Delete the `_instructions` key when a file is finished.
- Keep a `"split"` out of the labels: the gold set is for evaluation only, never training.
