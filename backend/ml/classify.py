"""
Frozen resume-category classifier loader (ML Training Master Plan Section 2.8).

This is the only file in ml/ the live app imports. It loads whatever
artifact scripts/train_classifier.py last produced and predicts a category
-- or returns None if no artifact exists yet, so the app degrades exactly
the way the SBERT-vs-fallback semantic backend already does (nlp_pipeline/
matching_engine.py): report what's actually active, never silently fake a
prediction. The model is never retrained inside a request (Section 2.8:
"never retrain this classifier silently as part of the live application").
"""

from __future__ import annotations
from pathlib import Path

ARTIFACT_PATH = Path(__file__).resolve().parent / "artifacts" / "resume_category_classifier.joblib"

_cached_model = None
_cache_checked = False


def _load() -> object | None:
    global _cached_model, _cache_checked
    if _cache_checked:
        return _cached_model
    _cache_checked = True
    if ARTIFACT_PATH.exists():
        import joblib
        _cached_model = joblib.load(ARTIFACT_PATH)
    return _cached_model


def classifier_available() -> bool:
    return _load() is not None


def classify_resume_category(raw_text: str) -> str | None:
    """Predicts one of ml.taxonomy.CATEGORIES for this resume's raw text,
    or None if no trained artifact exists yet (nothing has been guessed --
    the caller should treat this exactly like "not classified", not like
    a real category)."""
    model = _load()
    if model is None or not (raw_text or "").strip():
        return None
    return model.predict([raw_text])[0]


def _reset_cache_for_tests() -> None:
    global _cached_model, _cache_checked
    _cached_model = None
    _cache_checked = False
