"""
Ranking-quality metrics (project documentation Section 12.2)
------------------------------------------------------------------
Precision@k, NDCG@k, and MRR against a manually labeled ground-truth set.
These functions are pure and dataset-agnostic -- they take a ranked list
of candidate identifiers and a set of identifiers judged "relevant", so
they're usable both for offline evaluation notebooks and for the
regression check on the feedback/re-weighting loop (Section 12.3).

Binary relevance is assumed (a candidate either is or isn't relevant to a
JD) since that's what Section 12.1's labeling methodology produces --
"relevant"/"not relevant" per resume per JD, not graded relevance.
"""

from __future__ import annotations
import math


def precision_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Of the top k ranked items, what fraction are relevant?
    Returns 0.0 if k <= 0 or the ranked list is empty."""
    if k <= 0 or not ranked_ids:
        return 0.0
    top_k = ranked_ids[:k]
    hits = sum(1 for item in top_k if item in relevant_ids)
    return hits / len(top_k)


def _dcg_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    dcg = 0.0
    for i, item in enumerate(ranked_ids[:k], start=1):
        rel = 1.0 if item in relevant_ids else 0.0
        dcg += rel / math.log2(i + 1)
    return dcg


def ndcg_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Normalized DCG@k: rewards relevant items appearing higher in the
    ranking, not just being present somewhere in the top k."""
    if not ranked_ids or not relevant_ids:
        return 0.0
    dcg = _dcg_at_k(ranked_ids, relevant_ids, k)
    ideal_ranking = list(relevant_ids) + [i for i in ranked_ids if i not in relevant_ids]
    idcg = _dcg_at_k(ideal_ranking, relevant_ids, k)
    return dcg / idcg if idcg > 0 else 0.0


def reciprocal_rank(ranked_ids: list[str], relevant_ids: set[str]) -> float:
    """1 / (rank of the first relevant item), or 0.0 if none appear."""
    for i, item in enumerate(ranked_ids, start=1):
        if item in relevant_ids:
            return 1.0 / i
    return 0.0


def evaluate_single_job(ranked_ids: list[str], relevant_ids: set[str]) -> dict:
    """Metrics for one JD's ranking against its labeled relevant set."""
    return {
        "precision_at_5": precision_at_k(ranked_ids, relevant_ids, 5),
        "precision_at_10": precision_at_k(ranked_ids, relevant_ids, 10),
        "ndcg_at_10": ndcg_at_k(ranked_ids, relevant_ids, 10),
        "reciprocal_rank": reciprocal_rank(ranked_ids, relevant_ids),
    }


def aggregate_metrics(per_job_metrics: list[dict]) -> dict:
    """Mean of each metric across multiple labeled JDs -- MRR is, by
    definition, the mean of per-query reciprocal ranks."""
    if not per_job_metrics:
        return {"precision_at_5": 0.0, "precision_at_10": 0.0, "ndcg_at_10": 0.0, "mrr": 0.0}
    n = len(per_job_metrics)
    return {
        "precision_at_5": sum(m["precision_at_5"] for m in per_job_metrics) / n,
        "precision_at_10": sum(m["precision_at_10"] for m in per_job_metrics) / n,
        "ndcg_at_10": sum(m["ndcg_at_10"] for m in per_job_metrics) / n,
        "mrr": sum(m["reciprocal_rank"] for m in per_job_metrics) / n,
    }


# Targets from project documentation Section 12.2.
METRIC_TARGETS = {
    "precision_at_5": 0.8,
    "precision_at_10": 0.7,
    "ndcg_at_10": 0.75,
    "mrr": 0.8,
}

# Regression-check tolerance for the feedback/re-weighting loop (Section 12.3).
REGRESSION_TOLERANCE = 0.05


def should_promote_weights(new_metrics: dict, baseline_metrics: dict, tolerance: float = REGRESSION_TOLERANCE) -> bool:
    """Section 12.3: promote new scoring weights only if they hold steady or
    improve on the fixed validation set; if any metric drops by more than
    `tolerance`, the caller should roll back to `baseline_metrics`' weights."""
    for key in METRIC_TARGETS:
        baseline = baseline_metrics.get(key, 0.0)
        new = new_metrics.get(key, 0.0)
        if baseline > 0 and (baseline - new) / baseline > tolerance:
            return False
    return True
