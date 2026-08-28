"""
Feedback-loop re-weighting heuristic tests (Section 5.4). Pure-function
tests -- no DB needed. The DB-facing orchestration is covered separately
in test_reweighting_service.py.
"""
import pytest

from nlp_pipeline.reweighting import (
    propose_weights, ScoreStats, InsufficientFeedbackError,
    MIN_FEEDBACK_SAMPLES, WEIGHT_STEP, MIN_WEIGHT, MAX_WEIGHT,
    propose_weights_trained, FeedbackExample, InsufficientTrainingDataError,
    MIN_SAMPLES_FOR_TRAINED_REWEIGHT, _split_by_candidate,
)


class TestInsufficientFeedback:
    def test_raises_below_minimum_sample_count(self):
        with pytest.raises(InsufficientFeedbackError):
            propose_weights("BA", ScoreStats(70, 80, 1), ScoreStats(60, 60, 1))

    def test_raises_when_only_hired_feedback_exists(self):
        with pytest.raises(InsufficientFeedbackError):
            propose_weights("BA", ScoreStats(70, 80, 10), ScoreStats(0, 0, 0))

    def test_raises_when_only_rejected_feedback_exists(self):
        with pytest.raises(InsufficientFeedbackError):
            propose_weights("BA", ScoreStats(0, 0, 0), ScoreStats(60, 60, 10))

    def test_succeeds_right_at_the_minimum_with_both_directions(self):
        n = MIN_FEEDBACK_SAMPLES // 2
        result = propose_weights("BA", ScoreStats(70, 80, n), ScoreStats(60, 60, n))
        assert result.hired_count == n
        assert result.rejected_count == n


class TestProposal:
    def test_nudges_semantic_weight_up_when_semantic_separates_better(self):
        # semantic gap = 80-50=30, keyword gap = 65-60=5 -- semantic clearly wins
        hired = ScoreStats(avg_keyword=65, avg_semantic=80, count=5)
        rejected = ScoreStats(avg_keyword=60, avg_semantic=50, count=5)
        result = propose_weights("BA", hired, rejected)
        assert result.proposed_semantic_weight > result.current_semantic_weight
        assert result.proposed_keyword_weight < result.current_keyword_weight
        assert round(result.proposed_keyword_weight + result.proposed_semantic_weight, 2) == 1.0

    def test_nudges_keyword_weight_up_when_keyword_separates_better(self):
        hired = ScoreStats(avg_keyword=85, avg_semantic=60, count=5)
        rejected = ScoreStats(avg_keyword=55, avg_semantic=58, count=5)
        result = propose_weights("BA", hired, rejected)
        assert result.proposed_keyword_weight > result.current_keyword_weight
        assert result.proposed_semantic_weight < result.current_semantic_weight

    def test_no_change_when_gaps_are_too_close_to_call(self):
        hired = ScoreStats(avg_keyword=70, avg_semantic=70, count=5)
        rejected = ScoreStats(avg_keyword=60, avg_semantic=60.2, count=5)
        result = propose_weights("BA", hired, rejected)
        assert result.proposed_keyword_weight == result.current_keyword_weight
        assert result.proposed_semantic_weight == result.current_semantic_weight
        assert "too close to call" in result.reason

    def test_weights_never_exceed_bounds_even_with_repeated_pressure(self):
        hired = ScoreStats(avg_keyword=50, avg_semantic=99, count=5)
        rejected = ScoreStats(avg_keyword=50, avg_semantic=10, count=5)
        # simulate repeatedly re-applying the same strong signal
        kw, sem = 0.4, 0.6
        for _ in range(20):
            result = propose_weights("BA", hired, rejected, current_keyword_weight=kw, current_semantic_weight=sem)
            kw, sem = result.proposed_keyword_weight, result.proposed_semantic_weight
        assert kw >= MIN_WEIGHT
        assert sem <= MAX_WEIGHT
        assert round(kw + sem, 2) == 1.0

    def test_weight_step_matches_documented_constant(self):
        hired = ScoreStats(avg_keyword=50, avg_semantic=90, count=5)
        rejected = ScoreStats(avg_keyword=50, avg_semantic=50, count=5)
        result = propose_weights("BA", hired, rejected)
        assert result.proposed_semantic_weight == round(0.6 + WEIGHT_STEP, 2)


def _make_examples(n_per_class: int, semantic_signal: bool) -> list[FeedbackExample]:
    """n_per_class hired + n_per_class rejected, distinct candidate_ids,
    with a clean separating signal on one score type -- synthetic data
    for testing the FITTING CODE's correctness, not a claim about real
    hiring outcomes."""
    examples = []
    cid = 1
    for _ in range(n_per_class):
        if semantic_signal:
            examples.append(FeedbackExample(candidate_id=cid, keyword_score=55, semantic_score=90, decision="hired"))
        else:
            examples.append(FeedbackExample(candidate_id=cid, keyword_score=90, semantic_score=55, decision="hired"))
        cid += 1
    for _ in range(n_per_class):
        if semantic_signal:
            examples.append(FeedbackExample(candidate_id=cid, keyword_score=55, semantic_score=20, decision="rejected"))
        else:
            examples.append(FeedbackExample(candidate_id=cid, keyword_score=20, semantic_score=55, decision="rejected"))
        cid += 1
    return examples


class TestTrainedUpgradeGating:
    """ML Training Master Plan Section 4.2: the trained path needs far more
    data than the heuristic before it's trustworthy."""

    def test_raises_below_minimum_sample_count(self):
        examples = _make_examples(n_per_class=5, semantic_signal=True)  # 10 total, well below the gate
        assert len(examples) < MIN_SAMPLES_FOR_TRAINED_REWEIGHT
        with pytest.raises(InsufficientTrainingDataError):
            propose_weights_trained("BA", examples)

    def test_gate_is_stricter_than_the_heuristics(self):
        assert MIN_SAMPLES_FOR_TRAINED_REWEIGHT > MIN_FEEDBACK_SAMPLES

    def test_raises_when_only_one_decision_class_present(self):
        examples = [
            FeedbackExample(candidate_id=i, keyword_score=70, semantic_score=70, decision="hired")
            for i in range(1, MIN_SAMPLES_FOR_TRAINED_REWEIGHT + 5)
        ]
        with pytest.raises(InsufficientTrainingDataError):
            propose_weights_trained("BA", examples)

    def test_succeeds_at_the_minimum(self):
        n = MIN_SAMPLES_FOR_TRAINED_REWEIGHT // 2 + 1
        examples = _make_examples(n_per_class=n, semantic_signal=True)
        result = propose_weights_trained("BA", examples)
        assert result.hired_count == n
        assert result.rejected_count == n


class TestTrainedUpgradeFit:
    def test_normalized_weights_sum_to_one_and_stay_in_bounds(self):
        examples = _make_examples(n_per_class=25, semantic_signal=True)
        result = propose_weights_trained("BA", examples)
        assert round(result.proposed_keyword_weight + result.proposed_semantic_weight, 2) == 1.0
        assert MIN_WEIGHT <= result.proposed_keyword_weight <= MAX_WEIGHT
        assert MIN_WEIGHT <= result.proposed_semantic_weight <= MAX_WEIGHT

    def test_semantic_signal_pushes_semantic_weight_up(self):
        examples = _make_examples(n_per_class=25, semantic_signal=True)
        result = propose_weights_trained("BA", examples)
        assert result.proposed_semantic_weight > result.proposed_keyword_weight

    def test_keyword_signal_pushes_keyword_weight_up(self):
        examples = _make_examples(n_per_class=25, semantic_signal=False)
        result = propose_weights_trained("BA", examples)
        assert result.proposed_keyword_weight > result.proposed_semantic_weight

    def test_reason_documents_the_fit(self):
        examples = _make_examples(n_per_class=25, semantic_signal=True)
        result = propose_weights_trained("BA", examples)
        assert "logistic regression" in result.reason
        assert "coefficients" in result.reason

    def test_is_deterministic_given_the_same_seed(self):
        examples = _make_examples(n_per_class=25, semantic_signal=True)
        a = propose_weights_trained("BA", examples, seed=42)
        b = propose_weights_trained("BA", examples, seed=42)
        assert a.proposed_keyword_weight == b.proposed_keyword_weight
        assert a.proposed_semantic_weight == b.proposed_semantic_weight


class TestCandidateBasedSplit:
    def test_no_candidate_appears_in_both_fit_and_holdout(self):
        examples = _make_examples(n_per_class=25, semantic_signal=True)
        fit, holdout = _split_by_candidate(examples, holdout_fraction=0.25, seed=42)
        fit_ids = {e.candidate_id for e in fit}
        holdout_ids = {e.candidate_id for e in holdout}
        assert fit_ids.isdisjoint(holdout_ids)
        assert fit_ids | holdout_ids == {e.candidate_id for e in examples}

    def test_a_candidates_multiple_feedback_rows_stay_together(self):
        """If the same candidate shows up twice (feedback on two different
        JDs in the same category), both rows must land on the same side of
        the split -- splitting by row instead of by candidate is exactly
        the leakage Section 4.2 warns against."""
        examples = _make_examples(n_per_class=20, semantic_signal=True)
        # duplicate candidate_id=1's row under a different score pair
        examples.append(FeedbackExample(candidate_id=1, keyword_score=60, semantic_score=85, decision="hired"))
        fit, holdout = _split_by_candidate(examples, holdout_fraction=0.3, seed=7)
        candidate_1_in_fit = any(e.candidate_id == 1 for e in fit)
        candidate_1_in_holdout = any(e.candidate_id == 1 for e in holdout)
        assert candidate_1_in_fit != candidate_1_in_holdout  # in exactly one, never both
