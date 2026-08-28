"""
Matching Engine (project documentation Section 5.2)
------------------------------------------------------
composite_score = 0.4 x keyword_score (TF-IDF)  +  0.6 x semantic_score

Why hybrid, not keyword-only:
  A pure keyword match cannot connect a resume phrase like "coordinated
  cross-functional teams" to a JD requirement of "stakeholder management" --
  the two share no common words. The semantic component closes that gap.

Semantic backend (documented, not hidden):
  Production target (see design doc Section 3.4): Sentence-BERT
  (all-MiniLM-L6-v2) via `sentence-transformers`. That model is downloaded
  from huggingface.co at first run.
  This repository auto-detects what's available at runtime and is
  transparent about which one is active (see `semantic_backend_name()`):
    1. sentence-transformers (SBERT)  -- used if installed and the model
       downloads successfully (best quality; requires internet access to
       huggingface.co).
    2. spaCy word-vector average similarity (`en_core_web_md`) -- solid
       fallback with real static word vectors, no external model download
       beyond the spaCy model itself.
    3. TF-IDF-only -- final fallback; semantic_score == keyword_score in
       this mode. The system still runs, but loses the "understands
       meaning, not just words" capability -- this is flagged explicitly
       in the UI so nobody mistakes it for the full hybrid model.
Run `python -m nlp_pipeline.matching_engine --selftest` to see which
backend is active in your environment.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .preprocess import preprocess_for_vectorizer
from .extractor import CandidateProfile, get_nlp

KEYWORD_WEIGHT = 0.4
SEMANTIC_WEIGHT = 0.6

CONFIDENCE_BANDS = [
    (65.0, 100.0, "High Confidence Match"),
    (50.0, 64.999, "Moderate Match — Review Recommended"),
    (35.0, 49.999, "Partial / Weak Match — Secondary Pool"),
    (0.0, 34.999, "No Match — Irrelevant"),
]


def confidence_label(score: float) -> str:
    for low, high, label in CONFIDENCE_BANDS:
        if low <= score <= high:
            return label
    return "Unscored"


@dataclass
class JobDescription:
    title: str
    raw_text: str
    required_skills: list[str] = field(default_factory=list)
    min_experience: float = 0.0


@dataclass
class MatchResult:
    candidate_filename: str
    candidate_name: str | None
    keyword_score: float
    semantic_score: float
    composite_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    confidence: str
    experience_years: float


# ---------------------------------------------------------------- backends

@lru_cache(maxsize=1)
def _try_load_sbert():
    """Attempt to load Sentence-BERT. Returns the model or None if unavailable."""
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        return model
    except Exception:  # noqa: BLE001 -- any failure (not installed, no internet, etc.) -> fallback
        return None


@lru_cache(maxsize=1)
def _spacy_has_vectors() -> bool:
    nlp = get_nlp()
    return nlp.meta.get("vectors", {}).get("vectors", 0) > 0


def semantic_backend_name() -> str:
    if _try_load_sbert() is not None:
        return "sentence-transformers (all-MiniLM-L6-v2)"
    if _spacy_has_vectors():
        return "spaCy word-vector average (en_core_web_md) -- SBERT fallback"
    return "TF-IDF only -- no semantic backend available (see module docstring)"


def _tfidf_weighted_vector(nlp, text: str, idf_lookup: dict[str, float]) -> np.ndarray | None:
    """
    TF-IDF-weighted average of spaCy word vectors -- a standard, well-known
    technique for building a document-level embedding out of static word
    vectors that is meaningfully more discriminative than naive averaging.

    Naive averaging (`doc.similarity()`) is dominated by common English
    words shared by almost any two professional documents, which collapses
    similarity scores for unrelated resumes/JDs into a narrow, uninformative
    band near the top of the scale. Down-weighting common words and
    up-weighting rare/distinctive words (via TF-IDF) fixes that collapse
    without requiring a downloaded transformer model.
    """
    doc = nlp(text[:20_000])
    vectors, weights = [], []
    for token in doc:
        if token.is_stop or token.is_punct or not token.has_vector or token.vector_norm == 0:
            continue
        weight = idf_lookup.get(token.lemma_.lower(), 1.0)
        vectors.append(token.vector)
        weights.append(weight)
    if not vectors:
        return None
    vectors = np.array(vectors)
    weights = np.array(weights).reshape(-1, 1)
    weighted = (vectors * weights).sum(axis=0) / weights.sum()
    return weighted


def _build_corpus_idf(corpus_key: tuple[str, ...]) -> dict:
    """Builds an IDF lookup over a batch of documents so rare/distinctive terms
    (e.g. 'stakeholder', 'kubernetes') get weighted higher than common words
    (e.g. 'experience', 'team') when building the weighted vector above."""
    vectorizer = TfidfVectorizer(min_df=1, use_idf=True)
    vectorizer.fit([preprocess_for_vectorizer(t) for t in corpus_key])
    return dict(zip(vectorizer.get_feature_names_out(), vectorizer.idf_))


def _semantic_similarity(text_a: str, text_b: str, idf_lookup: dict | None = None) -> float:
    """Returns a 0-1 similarity score using the best available backend."""
    sbert = _try_load_sbert()
    if sbert is not None:
        emb = sbert.encode([text_a, text_b])
        sim = cosine_similarity([emb[0]], [emb[1]])[0][0]
        return float(max(0.0, min(1.0, sim)))

    if _spacy_has_vectors():
        nlp = get_nlp()
        idf_lookup = idf_lookup or {}
        vec_a = _tfidf_weighted_vector(nlp, text_a, idf_lookup)
        vec_b = _tfidf_weighted_vector(nlp, text_b, idf_lookup)
        if vec_a is not None and vec_b is not None:
            sim = cosine_similarity([vec_a], [vec_b])[0][0]
            return float(max(0.0, min(1.0, sim)))

    return None  # signals "no semantic backend" to the caller


# ---------------------------------------------------------------- scoring

def _keyword_score(resume_text: str, jd_text: str) -> float:
    """TF-IDF cosine similarity between resume and JD, scaled to 0-100."""
    corpus = [preprocess_for_vectorizer(resume_text), preprocess_for_vectorizer(jd_text)]
    if not any(corpus):
        return 0.0
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
    try:
        tfidf = vectorizer.fit_transform(corpus)
    except ValueError:
        return 0.0
    sim = cosine_similarity(tfidf[0], tfidf[1])[0][0]
    return round(float(sim) * 100, 1)


def score_candidate(
    profile: CandidateProfile,
    jd: JobDescription,
    idf_lookup: dict | None = None,
    keyword_weight: float = KEYWORD_WEIGHT,
    semantic_weight: float = SEMANTIC_WEIGHT,
) -> MatchResult:
    """keyword_weight/semantic_weight default to the documented 0.4/0.6 blend
    but are overridable -- the feedback loop (Section 5.4/12.3) proposes
    per-category weights based on recruiter hire/reject decisions, gated by
    a regression check before ever actually being used here. See
    nlp_pipeline/reweighting.py."""
    keyword = _keyword_score(profile.raw_text, jd.raw_text)

    sem = _semantic_similarity(profile.raw_text, jd.raw_text, idf_lookup=idf_lookup)
    if sem is None:
        # No semantic backend available at all -- degrade gracefully to keyword-only,
        # and be explicit about it rather than silently pretending it's hybrid.
        semantic = keyword
    else:
        semantic = round(sem * 100, 1)

    composite = round(keyword_weight * keyword + semantic_weight * semantic, 1)

    matched = sorted(set(profile.skills) & set(jd.required_skills))
    missing = sorted(set(jd.required_skills) - set(profile.skills))

    return MatchResult(
        candidate_filename=profile.filename,
        candidate_name=profile.full_name,
        keyword_score=keyword,
        semantic_score=semantic,
        composite_score=composite,
        matched_skills=matched,
        missing_skills=missing,
        confidence=confidence_label(composite),
        experience_years=profile.experience_years,
    )


def rank_candidates(
    profiles: list[CandidateProfile],
    jd: JobDescription,
    keyword_weight: float = KEYWORD_WEIGHT,
    semantic_weight: float = SEMANTIC_WEIGHT,
) -> list[MatchResult]:
    # Build one IDF lookup over the whole batch (all resumes + the JD) so rare,
    # distinctive terms are correctly up-weighted relative to this specific
    # batch rather than some fixed external corpus -- see _build_corpus_idf docstring.
    corpus = tuple([p.raw_text for p in profiles] + [jd.raw_text])
    idf_lookup = _build_corpus_idf(corpus) if _spacy_has_vectors() and _try_load_sbert() is None else {}

    results = [
        score_candidate(p, jd, idf_lookup=idf_lookup, keyword_weight=keyword_weight, semantic_weight=semantic_weight)
        for p in profiles
    ]
    # Deterministic tie-break (Section 8.3): composite score first, then semantic
    # score (rewards genuine meaning-match over a keyword-heavy tie), then
    # filename as a stable final tiebreaker so repeated runs never reorder ties.
    results.sort(key=lambda r: (-r.composite_score, -r.semantic_score, r.candidate_filename))
    return results


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        print(f"Active semantic backend: {semantic_backend_name()}")
        a = "coordinated cross-functional teams and communicated with senior stakeholders"
        b = "stakeholder management"
        sim = _semantic_similarity(a, b)
        print(f"Sample semantic similarity ('{a}' vs '{b}'): "
              f"{'N/A' if sim is None else round(sim, 3)}")
