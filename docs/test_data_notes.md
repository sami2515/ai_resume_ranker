# Test Data Notes (project documentation Section 8.4)

## Dataset

`datasets/resumes/` — the organizer-provided 228 `.docx` resumes, unmodified,
spanning Full Stack Developer, Business Analyst, Project Manager, and
Software Engineer roles.

## Test job descriptions

`datasets/test_jds/` — 4 test JDs used throughout development and for the
final demo:

- `full_stack_developer.txt`
- `business_analyst.txt`
- `project_manager.txt`
- `mismatched_marine_biologist.txt` — deliberately unrelated to every resume
  in the dataset, to exercise the "no strong matches" UI state (Section 8.3).

## Split plan

Recommended: ~80% of the 229 resumes for pipeline development/tuning, ~20%
(at least 10 per role category) held out purely for final validation and the
recorded demo — see `notebooks/01_dataset_exploration.ipynb` for the resume
list to split from.

The held-out validation subset (recommended 30-40 resumes, at least 10 per
category) also becomes the manually-labeled ground-truth set for Precision@k
/ NDCG / MRR (Section 12.1-12.2) — **label those once, before tuning, and
never use them for tuning** so the reported accuracy numbers stay honest.

## Status

Not yet done: the actual 80/20 split and the manual relevance labeling.
Planned for Phase 2-3 alongside the matching engine work, once the team has
a fixed set of test JDs to label against (the 3 role-matched JDs above).
