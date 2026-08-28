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

## Validation Guidelines

The held-out validation subset (30-40 resumes, at least 10 per category)
serves as the reference ground-truth set for Precision@k / NDCG / MRR
(Section 12.1-12.2) to evaluate candidate relevance against test JDs.
