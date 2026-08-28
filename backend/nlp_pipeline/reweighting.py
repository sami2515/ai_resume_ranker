"""
Feedback-loop re-weighting heuristic (project documentation Section 5.4)
----------------------------------------------------------------------------
Pure functions only -- no DB/filesystem access, so this is directly
unit-testable. The DB-facing orchestration (pulling feedback + match
results per category, persisting the outcome, running the Section 12.3
regression check) lives in services.py, which calls propose_weights() and
nothing else from here.

The heuristic, in plain terms: for a job category, compare the average
keyword_score and average semantic_score of candidates recruiters hired
vs. rejected. Whichever score type separates "hired" from "rejected" more
(a bigger gap) is treated as the more predictive signal for that category,
and its weight is nudged up by one fixed step -- not fit via gradient
descent or any real training procedure. That's a deliberate scope choice
(see design doc Section 5.4: "without requiring a full production MLOps
setup"), not a placeholder for something more sophisticated left unbuilt.
"""

from __future__ import annotations
from dataclasses import dataclass

DEFAULT_KEYWORD_WEIGHT = 0.4
DEFAULT_SEMANTIC_WEIGHT = 0.6

WEIGHT_STEP = 0.05
MIN_WEIGHT = 0.2
MAX_WEIGHT = 0.8

# Below this many total (hired + rejected) feedback samples for a category,
# any proposed nudge would be noise, not signal -- refuse to propose at all.
MIN_FEEDBACK_SAMPLES = 6


@dataclass
class ScoreStats:
    avg_keyword: float
    avg_semantic: float
    count: int


@dataclass
class ReweightProposal:
    category: str
    current_keyword_weight: float
    current_semantic_weight: float
    proposed_keyword_weight: float
    proposed_semantic_weight: float
    hired_count: int
    rejected_count: int
    reason: str


class InsufficientFeedbackError(Exception):
    """Raised when there isn't enough feedback yet to propose a change."""


# ---------------------------------------------------------------------------
# Optional upgrade (ML Training Master Plan Section 4): reframe the nudge
# above as a tiny, genuinely trained 2-feature logistic regression instead
# of a hand-picked step size. Deliberately optional -- Section 4.3 is
# explicit that the heuristic above remains a legitimate, defensible design
# on its own. This path needs far more data before it's trustworthy (a
# fitted model, unlike a fixed nudge, can overfit two coefficients to
# noise), so it stays inert until MIN_SAMPLES_FOR_TRAINED_REWEIGHT is met.

MIN_SAMPLES_FOR_TRAINED_REWEIGHT = 35


@dataclass
class FeedbackExample:
    candidate_id: int
    keyword_score: float
    semantic_score: float
    decision: str  # "hired" | "rejected"


class InsufficientTrainingDataError(Exception):
    """Raised when there isn't enough feedback to safely fit (not just
    nudge) a model -- distinct from InsufficientFeedbackError's lower bar
    for the heuristic, per Section 4.2's higher minimum-sample gate."""


def _split_by_candidate(examples: list[FeedbackExample], holdout_fraction: float, seed: int):
    """Splits by unique candidate_id, not by row (Section 4.2) -- a
    candidate who left feedback on multiple JDs must land entirely in the
    fit set or entirely in the holdout set, never both, or the holdout
    check would leak information about a candidate the model already saw."""
    import random

    candidate_ids = sorted({e.candidate_id for e in examples})
    rng = random.Random(seed)
    rng.shuffle(candidate_ids)
    n_holdout = max(1, round(len(candidate_ids) * holdout_fraction))
    holdout_ids = set(candidate_ids[:n_holdout])
    fit = [e for e in examples if e.candidate_id not in holdout_ids]
    holdout = [e for e in examples if e.candidate_id in holdout_ids]
    return fit, holdout


def propose_weights_trained(
    category: str,
    examples: list[FeedbackExample],
    current_keyword_weight: float = DEFAULT_KEYWORD_WEIGHT,
    current_semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT,
    seed: int = 42,
) -> ReweightProposal:
    """Fits LogisticRegression(keyword_score, semantic_score -> hired) with
    L2 regularization (Section 4.2 -- exactly the situation regularization
    exists for, with only two features and a small sample size), and turns
    its normalized coefficients into new composite weights. The caller is
    still responsible for running this proposal through the same
    regression-gated ScoringWeights promotion as the heuristic path --
    fitting a model doesn't exempt it from that safety net (Section 4.2)."""
    hired_n = sum(1 for e in examples if e.decision == "hired")
    rejected_n = sum(1 for e in examples if e.decision == "rejected")
    total = hired_n + rejected_n
    if total < MIN_SAMPLES_FOR_TRAINED_REWEIGHT:
        raise InsufficientTrainingDataError(
            f"Only {total} feedback example(s) for category '{category}' -- the trained-model "
            f"upgrade path needs at least {MIN_SAMPLES_FOR_TRAINED_REWEIGHT} (Section 4.2), well above "
            f"the heuristic's {MIN_FEEDBACK_SAMPLES}-sample floor, because fitting two coefficients "
            f"needs more data to avoid overfitting to noise than a fixed nudge does. Use the "
            f"heuristic (propose_weights) until then."
        )
    if hired_n == 0 or rejected_n == 0:
        raise InsufficientTrainingDataError(
            f"Category '{category}' has feedback in only one direction ({hired_n} hired, "
            f"{rejected_n} rejected) -- can't fit a classifier without both classes."
        )

    from sklearn.linear_model import LogisticRegression

    fit_examples, holdout_examples = _split_by_candidate(examples, holdout_fraction=0.25, seed=seed)
    # Degenerate split (e.g. one candidate dominates the sample): fall back
    # to using everything to fit, skip the holdout diagnostic rather than
    # fail outright -- the outer regression gate still protects promotion.
    if len({e.decision for e in fit_examples}) < 2:
        fit_examples, holdout_examples = examples, []

    X_fit = [[e.keyword_score, e.semantic_score] for e in fit_examples]
    y_fit = [1 if e.decision == "hired" else 0 for e in fit_examples]

    # L2 regularization is scikit-learn's own default for LogisticRegression
    # (Section 4.2: "Apply L2 regularization (scikit-learn's default)") --
    # left unset rather than passed explicitly since newer scikit-learn
    # versions deprecate the redundant penalty="l2" spelling in favor of
    # just relying on the default.
    model = LogisticRegression(random_state=seed)
    model.fit(X_fit, y_fit)

    holdout_accuracy = None
    if holdout_examples:
        X_holdout = [[e.keyword_score, e.semantic_score] for e in holdout_examples]
        y_holdout = [1 if e.decision == "hired" else 0 for e in holdout_examples]
        holdout_accuracy = model.score(X_holdout, y_holdout)

    keyword_coef, semantic_coef = model.coef_[0]
    # A negative coefficient means that score type moved *against* hiring
    # in this sample -- floor at a small positive value rather than let it
    # go negative or zero out a weight entirely, since composite_score
    # must stay a sensible weighted blend of both components.
    keyword_mag = max(abs(keyword_coef), 1e-6)
    semantic_mag = max(abs(semantic_coef), 1e-6)
    total_mag = keyword_mag + semantic_mag
    new_keyword = max(MIN_WEIGHT, min(MAX_WEIGHT, round(keyword_mag / total_mag, 2)))
    new_semantic = round(1.0 - new_keyword, 2)

    reason = (
        f"trained logistic regression on {len(fit_examples)} fit example(s) "
        f"({'+' + str(len(holdout_examples)) + ' held out by candidate' if holdout_examples else 'no holdout split possible'}); "
        f"coefficients: keyword={keyword_coef:.3f}, semantic={semantic_coef:.3f}"
        + (f"; holdout accuracy={holdout_accuracy:.2f}" if holdout_accuracy is not None else "")
        + f" -- normalized to keyword={new_keyword}, semantic={new_semantic}."
    )

    return ReweightProposal(
        category=category,
        current_keyword_weight=current_keyword_weight,
        current_semantic_weight=current_semantic_weight,
        proposed_keyword_weight=new_keyword,
        proposed_semantic_weight=new_semantic,
        hired_count=hired_n,
        rejected_count=rejected_n,
        reason=reason,
    )


def propose_weights(
    category: str,
    hired: ScoreStats,
    rejected: ScoreStats,
    current_keyword_weight: float = DEFAULT_KEYWORD_WEIGHT,
    current_semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT,
) -> ReweightProposal:
    total = hired.count + rejected.count
    if total < MIN_FEEDBACK_SAMPLES:
        raise InsufficientFeedbackError(
            f"Only {total} feedback sample(s) for category '{category}' "
            f"(need at least {MIN_FEEDBACK_SAMPLES}: {MIN_FEEDBACK_SAMPLES // 2} hired + "
            f"{MIN_FEEDBACK_SAMPLES // 2} rejected as a rough floor)."
        )
    if hired.count == 0 or rejected.count == 0:
        raise InsufficientFeedbackError(
            f"Category '{category}' has feedback in only one direction "
            f"({hired.count} hired, {rejected.count} rejected) -- can't measure which "
            f"score type separates hires from rejects without both."
        )

    keyword_gap = hired.avg_keyword - rejected.avg_keyword
    semantic_gap = hired.avg_semantic - rejected.avg_semantic

    if abs(semantic_gap - keyword_gap) < 0.5:  # points; too close to call
        return ReweightProposal(
            category=category,
            current_keyword_weight=current_keyword_weight,
            current_semantic_weight=current_semantic_weight,
            proposed_keyword_weight=current_keyword_weight,
            proposed_semantic_weight=current_semantic_weight,
            hired_count=hired.count,
            rejected_count=rejected.count,
            reason=f"keyword gap ({keyword_gap:.1f}) and semantic gap ({semantic_gap:.1f}) "
                   f"are too close to call -- no change proposed.",
        )

    if semantic_gap > keyword_gap:
        new_semantic = min(current_semantic_weight + WEIGHT_STEP, MAX_WEIGHT)
        new_keyword = round(1.0 - new_semantic, 2)
        reason = (f"semantic score separates hired ({hired.avg_semantic:.1f}) from rejected "
                  f"({rejected.avg_semantic:.1f}) more than keyword score does "
                  f"({hired.avg_keyword:.1f} vs {rejected.avg_keyword:.1f}) -- nudging semantic weight up.")
    else:
        new_keyword = min(current_keyword_weight + WEIGHT_STEP, MAX_WEIGHT)
        new_semantic = round(1.0 - new_keyword, 2)
        reason = (f"keyword score separates hired ({hired.avg_keyword:.1f}) from rejected "
                  f"({rejected.avg_keyword:.1f}) more than semantic score does "
                  f"({hired.avg_semantic:.1f} vs {rejected.avg_semantic:.1f}) -- nudging keyword weight up.")

    new_keyword = max(MIN_WEIGHT, min(MAX_WEIGHT, new_keyword))
    new_semantic = round(1.0 - new_keyword, 2)

    return ReweightProposal(
        category=category,
        current_keyword_weight=current_keyword_weight,
        current_semantic_weight=current_semantic_weight,
        proposed_keyword_weight=new_keyword,
        proposed_semantic_weight=new_semantic,
        hired_count=hired.count,
        rejected_count=rejected.count,
        reason=reason,
    )
