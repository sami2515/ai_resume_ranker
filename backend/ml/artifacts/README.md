# Trained model artifacts

This directory holds the frozen, versioned output of `scripts/train_classifier.py`:

- `resume_category_classifier.joblib` — the fitted TF-IDF + (Logistic Regression or Linear SVM) pipeline, whichever won the Section 2.5/2.6 comparison.
- `resume_category_classifier.meta.json` — the evidence for how it was chosen: cross-validation scores (mean + std), the winning hyperparameters, the per-class report, the confusion matrix, label counts, and library versions at training time (Section 2.8/7).

Both files are committed once real training has happened — **never ship a model artifact without the evidence of how it was chosen** (Section 2.8). Nothing is here yet because Section 2.2's labeling step needs a human reading real resumes; see `docs/ml_training/README.md` for the full workflow.

`backend/ml/classify.py` loads whatever is here at runtime and returns `None` if this directory is empty — exactly like the semantic-backend fallback, the app is honest about "not classified yet" rather than guessing.
