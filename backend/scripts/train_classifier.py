"""
Resume category classifier -- training runner (ML Training Master Plan Section 2)
-----------------------------------------------------------------------------------
Trains the supervised resume category classifier: stratified 5-fold CV,
model comparison (TF-IDF + Logistic Regression vs. TF-IDF + Linear SVM),
hyperparameter grid search, out-of-fold confusion matrix, and frozen artifact.

Expects ground-truth labels in docs/category_labels.json (see
scripts/build_labeling_worksheet.py and scripts/check_labeling_agreement.py).

Usage (from repo root):
    python backend/scripts/train_classifier.py
"""

from __future__ import annotations
import csv
import json
import platform
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from nlp_pipeline.parser import parse_resume, ResumeParseError
from nlp_pipeline.extractor import extract_profile
from ml.taxonomy import CATEGORIES, OTHER_GENERAL, MIN_CATEGORY_COUNT_FOR_TRAINING, validate_category

LABELS_PATH = REPO_ROOT / "docs" / "category_labels.json"
DATASET_DIR = REPO_ROOT / "datasets" / "resumes"
ARTIFACT_DIR = REPO_ROOT / "backend" / "ml" / "artifacts"
ARTIFACT_PATH = ARTIFACT_DIR / "resume_category_classifier.joblib"
META_PATH = ARTIFACT_DIR / "resume_category_classifier.meta.json"
EXPERIMENTS_LOG = REPO_ROOT / "docs" / "ml_training" / "experiments_log.csv"

RANDOM_SEED = 42
N_FOLDS = 5
MIN_TOTAL_EXAMPLES = 20  # below this, 5-fold CV is close to meaningless

# Section 2.6: the grids tuned for each family.
TFIDF_GRID = {
    "tfidf__max_features": [500, 1000, 2000],
    "tfidf__ngram_range": [(1, 1), (1, 2)],
    "tfidf__min_df": [1, 2],
}
LOGREG_GRID = {**TFIDF_GRID, "clf__C": [0.01, 0.1, 1, 10]}
SVM_GRID = {**TFIDF_GRID, "clf__C": [0.01, 0.1, 1, 10]}


def load_labels() -> dict[str, str]:
    if not LABELS_PATH.exists():
        print(f"No labeled data found at {LABELS_PATH}.")
        print("Section 2.2 requires resumes labeled by a human reading the body text (not the")
        print("filename), with a second independent pass and an agreement check. To produce it:")
        print("  1. python backend/scripts/build_labeling_worksheet.py --out docs/labels_person_a.json")
        print("  2. Have a second person independently do the same into docs/labels_person_b.json")
        print("  3. python backend/scripts/check_labeling_agreement.py docs/labels_person_a.json docs/labels_person_b.json")
        print("  4. Resolve disagreements together, then save the final agreed labels to")
        print(f"     {LABELS_PATH} as {{\"entries\": {{filename: category}}}} (or the worksheet shape).")
        raise SystemExit(1)

    data = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    entries = data.get("entries", data)
    labels = {}
    for filename, value in entries.items():
        category = value["category"] if isinstance(value, dict) else value
        if not category:
            continue
        validate_category(category)  # fails loudly on a typo'd/invalid category
        labels[filename] = category
    if len(labels) < MIN_TOTAL_EXAMPLES:
        print(f"Only {len(labels)} labeled example(s) -- need at least {MIN_TOTAL_EXAMPLES} for "
              f"{N_FOLDS}-fold cross-validation to mean anything. Label more resumes first.")
        raise SystemExit(1)
    return labels


def merge_small_categories(labels: dict[str, str]) -> dict[str, str]:
    counts = Counter(labels.values())
    print("Label counts (before merge):")
    for cat in CATEGORIES:
        print(f"  {cat:<24} {counts.get(cat, 0)}")

    small = {cat for cat, n in counts.items() if n < MIN_CATEGORY_COUNT_FOR_TRAINING and cat != OTHER_GENERAL}
    if not small:
        return labels

    print(f"\nCategories below {MIN_CATEGORY_COUNT_FOR_TRAINING} examples get folded into "
          f"'{OTHER_GENERAL}' for classifier training (Section 2.4): {sorted(small)}")
    merged = {f: (OTHER_GENERAL if cat in small else cat) for f, cat in labels.items()}
    print("Label counts (after merge):")
    for cat, n in sorted(Counter(merged.values()).items()):
        print(f"  {cat:<24} {n}")
    return merged


def load_texts(labels: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    texts, y, filenames = [], [], []
    for filename, category in labels.items():
        path = DATASET_DIR / filename
        if not path.exists():
            print(f"  skipping {filename}: not found in {DATASET_DIR}")
            continue
        try:
            profile = extract_profile(parse_resume(path))
        except ResumeParseError as e:
            print(f"  skipping {filename}: {e}")
            continue
        texts.append(profile.raw_text)
        y.append(category)
        filenames.append(filename)
    return texts, y, filenames


def build_families():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.svm import LinearSVC
    from sklearn.pipeline import Pipeline

    logreg = Pipeline([
        ("tfidf", TfidfVectorizer()),
        ("clf", LogisticRegression(class_weight="balanced", random_state=RANDOM_SEED, max_iter=2000)),
    ])
    svm = Pipeline([
        ("tfidf", TfidfVectorizer()),
        ("clf", LinearSVC(class_weight="balanced", random_state=RANDOM_SEED, max_iter=5000)),
    ])
    return {"TF-IDF + Logistic Regression": (logreg, LOGREG_GRID), "TF-IDF + Linear SVM": (svm, SVM_GRID)}


def log_experiments(model_name: str, cv_results: dict, n_examples: int) -> None:
    EXPERIMENTS_LOG.parent.mkdir(parents=True, exist_ok=True)
    is_new = not EXPERIMENTS_LOG.exists()
    with EXPERIMENTS_LOG.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["timestamp_utc", "model_family", "n_examples", "params", "mean_f1_macro", "std_f1_macro"])
        timestamp = datetime.now(timezone.utc).isoformat()
        for params, mean, std in zip(cv_results["params"], cv_results["mean_test_score"], cv_results["std_test_score"]):
            writer.writerow([timestamp, model_name, n_examples, json.dumps(params), round(mean, 4), round(std, 4)])


def main():
    print("=== Resume Category Classifier -- Training (ML Training Master Plan Section 2) ===\n")
    raw_labels = load_labels()
    labels = merge_small_categories(raw_labels)

    print("\nParsing labeled resumes...")
    X_text, y, filenames = load_texts(labels)
    print(f"Loaded {len(X_text)}/{len(labels)} labeled resumes with usable text.\n")

    if len(set(y)) < 2:
        print("Only one class remains after merging -- can't train a classifier on a single label.")
        raise SystemExit(1)

    from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_predict
    from sklearn.metrics import classification_report, confusion_matrix, f1_score
    from sklearn import __version__ as sklearn_version
    import numpy
    import joblib

    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_SEED)

    results = {}
    for name, (pipeline, grid) in build_families().items():
        print(f"Grid-searching {name} ({len(grid.get('clf__C', [None]))} x "
              f"{len(TFIDF_GRID['tfidf__max_features'])} x {len(TFIDF_GRID['tfidf__ngram_range'])} x "
              f"{len(TFIDF_GRID['tfidf__min_df'])} configurations, {N_FOLDS}-fold CV)...")
        gs = GridSearchCV(pipeline, grid, cv=skf, scoring="f1_macro", n_jobs=-1)
        gs.fit(X_text, y)
        log_experiments(name, gs.cv_results_, len(X_text))
        best_idx = gs.best_index_
        std = gs.cv_results_["std_test_score"][best_idx]
        print(f"  best: macro-F1 = {gs.best_score_:.3f} (+/- {std:.3f})  params={gs.best_params_}")
        results[name] = {"gs": gs, "std": std}

    winner_name = max(results, key=lambda n: results[n]["gs"].best_score_)
    winner = results[winner_name]["gs"]
    print(f"\nWinner: {winner_name} (macro-F1 = {winner.best_score_:.3f} +/- {results[winner_name]['std']:.3f})")

    # Honest out-of-fold confusion matrix: predict each fold with a model
    # that never saw that fold, using the winning hyperparameters -- not
    # gs.predict(), which would be scored on data some of it was fit on.
    from sklearn.base import clone
    winner_pipeline = clone(winner.estimator).set_params(**winner.best_params_)
    y_pred_oof = cross_val_predict(winner_pipeline, X_text, y, cv=skf)

    report = classification_report(y, y_pred_oof, output_dict=True, zero_division=0)
    labels_sorted = sorted(set(y) | set(y_pred_oof))
    cm = confusion_matrix(y, y_pred_oof, labels=labels_sorted)
    macro_f1_oof = f1_score(y, y_pred_oof, average="macro")

    print(f"\nOut-of-fold macro-F1: {macro_f1_oof:.3f}")
    print(classification_report(y, y_pred_oof, zero_division=0))
    print("Confusion matrix (rows=true, cols=predicted):")
    print("labels:", labels_sorted)
    for row_label, row in zip(labels_sorted, cm):
        print(f"  {row_label:<24} {list(row)}")

    # Refit the winner on ALL labeled data for the deployable artifact.
    final_model = clone(winner.estimator).set_params(**winner.best_params_)
    final_model.fit(X_text, y)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(final_model, ARTIFACT_PATH)

    version_tag = "v" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    meta = {
        "version": version_tag,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_family": winner_name,
        "best_params": {k: (list(v) if isinstance(v, tuple) else v) for k, v in winner.best_params_.items()},
        "cv_macro_f1_mean": round(winner.best_score_, 4),
        "cv_macro_f1_std": round(results[winner_name]["std"], 4),
        "out_of_fold_macro_f1": round(macro_f1_oof, 4),
        "per_class_report": report,
        "confusion_matrix": {"labels": labels_sorted, "matrix": cm.tolist()},
        "label_counts": dict(Counter(y)),
        "n_labeled_examples": len(X_text),
        "n_folds": N_FOLDS,
        "random_seed": RANDOM_SEED,
        "sklearn_version": sklearn_version,
        "numpy_version": numpy.__version__,
        "python_version": platform.python_version(),
        "note": "This repo has no git history at training time, so no commit hash is recorded here -- "
                "version/trained_at_utc plus this file are the traceability record instead (Section 7).",
    }
    META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"\nSaved model:    {ARTIFACT_PATH.relative_to(REPO_ROOT)}")
    print(f"Saved metadata: {META_PATH.relative_to(REPO_ROOT)}")
    print(f"Logged experiments: {EXPERIMENTS_LOG.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
