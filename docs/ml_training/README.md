# ML Training & Validation Workflow

Implements the *AI Resume Ranker — AI/ML Model Training & Validation Master Plan*. This is the step-by-step the team actually runs; the master plan document is the reasoning behind each step.

## What's trained here, and what deliberately isn't

Per the master plan's Section 1 table:

| Component | Trained? |
|---|---|
| Skill extraction (gazetteer + spaCy NER) | No — curated lookup + pretrained NER, not a fitting task |
| Keyword scoring (TF-IDF) | No — refit per ranking batch by design, not persisted |
| Semantic scoring (SBERT / spaCy fallback) | No, deliberately — see Section 3 of the master plan; 231 resumes is far too little to fine-tune without overfitting to this dataset's vocabulary |
| **Resume category classifier** | **Yes — the one component that's genuinely supposed to be a trained model.** This directory's whole purpose. |
| Composite weight re-weighting | Optionally — a default heuristic already ships (`nlp_pipeline/reweighting.py`); a trained-model upgrade path exists but needs far more feedback data than currently exists to be worth using (see "Optional: trained re-weighting" below). |

## 1. Label the data (Section 2.1/2.2)

The taxonomy is fixed in `backend/ml/taxonomy.py` — six categories, each with a one-line rule. Don't add a seventh mid-project; use "Other / General" for anything that doesn't fit.

```bash
# Person A labels everything
python backend/scripts/build_labeling_worksheet.py --out docs/labels_person_a.json

# Person B independently re-labels a random ~20% subset into a second file,
# without seeing person A's labels
python backend/scripts/build_labeling_worksheet.py --out docs/labels_person_b.json
# (then delete entries from person B's file outside the chosen 20% subset)

# Score agreement
python backend/scripts/check_labeling_agreement.py docs/labels_person_a.json docs/labels_person_b.json
```

Discuss every disagreement the agreement check prints, together, and sharpen the taxonomy rule in `backend/ml/taxonomy.py` if a disagreement reveals it was ambiguous. Once done, save the final, agreed set of labels as `docs/category_labels.json` (same shape as the worksheet — see `docs/category_labels_template.json`).

## 2. Train the classifier (Section 2.3–2.8)

```bash
python backend/scripts/train_classifier.py
```

One run does the whole rigorous pass: prints label counts and folds any category under `MIN_CATEGORY_COUNT_FOR_TRAINING` into "Other / General" (Section 2.4), grid-searches TF-IDF + Logistic Regression *and* TF-IDF + Linear SVM under stratified 5-fold CV (Section 2.5/2.6, logging every configuration tried to `docs/ml_training/experiments_log.csv`), picks the winner, computes an honest out-of-fold confusion matrix and per-class report (Section 2.7), refits on all labeled data, and saves the frozen artifact + full metadata to `backend/ml/artifacts/` (Section 2.8).

Paste the printed per-class precision/recall/F1, macro-F1, confusion matrix, and CV standard deviation directly into the final report — that's the evidence Section 2.7 requires, not a paraphrase of it.

The moment the artifact exists, `backend/ml/classify.py` picks it up automatically — new resume uploads get a `predicted_category` field (previously always `null`). Nothing else needs to change; this mirrors how the app already reports whichever semantic backend is actually active rather than assuming one.

## 3. Calibrate confidence-band thresholds (Section 3)

SBERT stays pretrained and frozen — don't fine-tune it (see the master plan's Section 3 reasoning). The legitimate calibration step is the composite-score cutoffs (currently 80/55) that decide the High/Moderate/Weak bands:

```bash
python backend/scripts/calibrate_thresholds.py
```

Needs `docs/validation_labels.json` to exist (see `docs/validation_labels_template.json` / the ML Engineering Plan Section 5.1). Prints precision/recall/F1 at each threshold in the sweep — use it to make a deliberate, evidence-backed choice about `CONFIDENCE_BANDS` in `nlp_pipeline/matching_engine.py`; the script doesn't edit that constant for you.

## 4. Optional: trained re-weighting upgrade (Section 4)

The feedback loop already ships with a safe, defensible heuristic (`propose_weights` in `nlp_pipeline/reweighting.py`, wired to `POST /api/feedback/reweight`). Section 4 shows a genuinely trained alternative — a 2-feature logistic regression fit on real recruiter hired/rejected decisions — wired to `POST /api/feedback/reweight-trained`.

It needs **at least 35 real hired+rejected feedback examples in one category** (`MIN_SAMPLES_FOR_TRAINED_REWEIGHT`, well above the heuristic's 6-sample floor — see Section 4.2 for why) before it will do anything but return `insufficient_feedback`. Both paths are promoted through the exact same Section 12.3 regression-gated `ScoringWeights` check, so neither can silently change live ranking behavior without first being verified against `docs/validation_labels.json`.

If there isn't time or data to exercise this before submission, that's fine — **say so explicitly** in the report per Section 4.3: the heuristic is a legitimate, simpler, lower-data-requirement design on its own, not an unfinished version of the trained path.

## 5. Consolidated evaluation (Section 5) and the failure-mode checklist (Section 6)

`docs/ml_training/zero_error_margin_checklist.md` tracks Section 8's full checklist item by item — what's already built as tooling/code (checked) versus what needs a human to actually do the labeling and run the scripts above (unchecked, with the exact command to run).

## Reproducibility notes (Section 7)

- Every script above fixes `RANDOM_SEED = 42` for cross-validation folds and model initialization.
- `docs/ml_training/experiments_log.csv` accumulates one row per hyperparameter configuration tried, across every training run — never delete old rows, that history is the evidence Section 2.6 asks for.
- `requirements.txt` intentionally keeps *version floors* (`scikit-learn>=1.5`, not an exact pin) rather than exact pins — an earlier exact pin (`numpy==1.26.4`) failed to install on Python 3.13 without a C compiler, a real bug hit during this project (see the top of `requirements.txt`). Exact reproducibility is instead captured per-artifact: every `resume_category_classifier.meta.json` records the exact `scikit-learn`/`numpy`/Python versions that specific model was trained under, which is what actually matters for tracing a given artifact's results back to its environment.
- Never overwrite `docs/category_labels.json` or `docs/validation_labels.json` in place if you relabel — copy to a `_v2` file first, so a metric quoted in an earlier report draft stays traceable to the exact data it was measured against.
