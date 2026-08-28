# Zero-Error-Margin Training Checklist

Tracks Section 8 of the ML Training Master Plan. "Tooling built" means the code exists and is tested; it is **not** the same as "done" for items that require a human to actually do something (labeling, running a script, reading a printed table into the report) — those stay unchecked with the exact next action until someone does it for real.

| # | Item | Status | Notes |
|---|---|---|---|
| 1 | Label taxonomy fixed and written down, with a one-line rule per category (2.1) | ✅ Done | `backend/ml/taxonomy.py` — 6 categories incl. required "Other / General" catch-all |
| 2 | All resumes labeled from body text, with a documented second-pass agreement check (2.2) | ⬜ Pending human labeling | Tooling ready: `scripts/build_labeling_worksheet.py`, `scripts/check_labeling_agreement.py`. Needs two team members to actually label. |
| 3 | Classifier trained with stratified k-fold CV; mean and std reported (2.3) | ⬜ Pending #2 | `scripts/train_classifier.py` does this automatically once `docs/category_labels.json` exists |
| 4 | Class imbalance explicitly measured and handled (2.4) | ✅ Tooling built | `train_classifier.py` prints per-category counts and auto-folds anything under `MIN_CATEGORY_COUNT_FOR_TRAINING` into "Other / General"; uses `class_weight="balanced"` for both model families |
| 5 | At least two model types compared, comparison shown not just the winner (2.5) | ✅ Tooling built | TF-IDF+LogisticRegression vs. TF-IDF+LinearSVM, both logged every run |
| 6 | Hyperparameter search logged in full (2.6) | ✅ Tooling built | Every `GridSearchCV` configuration + score appended to `docs/ml_training/experiments_log.csv` |
| 7 | Per-class P/R/F1, macro-F1, confusion matrix in the final report (2.7) | ⬜ Pending #2/#3 | Printed by `train_classifier.py` and saved to the model's `.meta.json` — copy into the report once a real run happens |
| 8 | SBERT deliberately left pretrained, reasoning stated (3) | ✅ Done | No fine-tuning code exists anywhere in `nlp_pipeline/`; reasoning documented in the master plan Section 3 and `docs/ml_training/README.md` |
| 9 | Composite-weight upgrade (4) has the same minimum-sample gate, regularization, and regression-gated promotion — or the heuristic is explicitly defended | ✅ Both built | `propose_weights_trained` (35-sample gate, candidate-based split, L2-regularized `LogisticRegression`) shares `_apply_reweight_proposal`'s Section 12.3 regression gate with the heuristic. Heuristic remains default/primary per Section 4.3 until real feedback volume exists. |
| 10 | Every metric anywhere states its exact validation-set size (5.3) | ⬜ Team discipline | Not something code can enforce — a reviewing habit for the report/blog/demo narration |
| 11 | Every Section 6 failure-mode has its guard actually implemented | ✅ Done | See table below |
| 12 | Random seeds fixed and documented; experiments log exists; library versions pinned (7) | ✅ Done (adapted) | `RANDOM_SEED = 42` everywhere; experiments log auto-created; exact versions captured per-artifact in `.meta.json` instead of via exact `requirements.txt` pins — see the README's reproducibility note for why |

## Section 6 failure-mode guards

| Failure mode | Guard | Where |
|---|---|---|
| Label leakage via filename | Worksheet is built from parsed body text; filenames never enter the labeling flow | `ml/labeling.py::build_labeling_worksheet`, tested in `tests/test_ml_taxonomy_and_labeling.py` |
| Train/test overlap | Feedback split by candidate identity, not by row | `nlp_pipeline/reweighting.py::_split_by_candidate`, tested in `tests/test_reweighting.py::TestCandidateBasedSplit` |
| Single lucky/unlucky split | Stratified 5-fold CV with std dev reported | `scripts/train_classifier.py` |
| Class imbalance hidden by accuracy | Macro-F1 + full confusion matrix always reported, accuracy never used alone | `scripts/train_classifier.py` |
| Overfitting a 2-feature model on tiny feedback data | 35-sample minimum gate + scikit-learn's default L2 regularization | `nlp_pipeline/reweighting.py::propose_weights_trained`, `MIN_SAMPLES_FOR_TRAINED_REWEIGHT` |
| Fine-tuning a large model on a tiny dataset | No fine-tuning code exists for SBERT or any transformer; classifier baselines are TF-IDF + linear models only | `nlp_pipeline/matching_engine.py`, `scripts/train_classifier.py` |
| Metric cherry-picking | Every grid configuration logged, not just the best | `docs/ml_training/experiments_log.csv` |
| Silent model drift | Regression-gated `ScoringWeights` promotion in front of both the heuristic and trained re-weighting paths | `services.py::_apply_reweight_proposal` |
| Unstated validation-set size | `evaluate_ranking.py` / `calibrate_thresholds.py` print the exact labeled-resume count alongside every number | `backend/scripts/*.py` |
