# Skill extraction evaluation

## SkillSpan test split (3569 sentences, human labels)

| System | TECH P | TECH R | TECH F1 | SOFT F1 | Micro F1 | Unseen-skill recall | ms/sentence |
|---|---:|---:|---:|---:|---:|---:|---:|
| dictionary | 0.620 | 0.171 | 0.268 | 0.000 | 0.155 | 0.000 | - |
| distilbert | 0.565 | 0.602 | 0.583 | 0.421 | 0.505 | 0.559 | 5.919 |
| bilstm_crf | 0.520 | 0.468 | 0.492 | 0.272 | 0.390 | 0.407 | 0.842 |

## Generated resumes (100 resumes, synthetic ground truth)

Set-level skill extraction on the project's 100 generated resumes. Ground truth is the generator's skill list; real skills mentioned in the text but not on that list count as false positives. These resumes were also used for error analysis when designing the parser's span filters (skip the education section, keep leading dots, drop vague phrases such as 'modern web technologies'), so this is not a blind test - the SkillSpan test split above is.

| System | Precision | Recall | F1 |
|---|---:|---:|---:|
| dictionary | 0.951 | 0.768 | 0.850 |
| distilbert_only | 0.952 | 0.826 | 0.884 |
| distilbert+dictionary | 0.939 | 0.933 | 0.936 |
| bilstm_crf_only | 0.930 | 0.790 | 0.855 |
| bilstm_crf+dictionary | 0.920 | 0.922 | 0.921 |
