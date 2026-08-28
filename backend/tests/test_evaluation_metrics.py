"""
Unit tests for the ranking-quality metrics (Section 12.2) using synthetic
rankings with known-by-hand expected values.
"""
import pytest
from pytest import approx as pytest_approx

from nlp_pipeline.evaluation import (
    precision_at_k, ndcg_at_k, reciprocal_rank, evaluate_single_job,
    aggregate_metrics, should_promote_weights,
)


class TestPrecisionAtK:
    def test_all_relevant_in_top_k(self):
        ranked = ["a", "b", "c", "d", "e"]
        relevant = {"a", "b", "c", "d", "e"}
        assert precision_at_k(ranked, relevant, 5) == 1.0

    def test_none_relevant(self):
        ranked = ["a", "b", "c"]
        relevant = {"x", "y"}
        assert precision_at_k(ranked, relevant, 3) == 0.0

    def test_partial_relevance(self):
        ranked = ["a", "b", "c", "d"]
        relevant = {"a", "c"}
        assert precision_at_k(ranked, relevant, 4) == 0.5

    def test_k_larger_than_list(self):
        ranked = ["a", "b"]
        relevant = {"a"}
        assert precision_at_k(ranked, relevant, 10) == 0.5  # divides by actual slice length

    def test_empty_ranked_list(self):
        assert precision_at_k([], {"a"}, 5) == 0.0


class TestNDCG:
    def test_perfect_ranking_scores_one(self):
        ranked = ["a", "b", "c"]
        relevant = {"a", "b", "c"}
        assert ndcg_at_k(ranked, relevant, 3) == pytest_approx(1.0)

    def test_relevant_item_lower_scores_less_than_perfect(self):
        perfect = ndcg_at_k(["a", "b", "x"], {"a", "b"}, 3)
        worse = ndcg_at_k(["x", "a", "b"], {"a", "b"}, 3)
        assert worse < perfect

    def test_no_relevant_items_is_zero(self):
        assert ndcg_at_k(["a", "b"], set(), 2) == 0.0


class TestReciprocalRank:
    def test_first_position_hit(self):
        assert reciprocal_rank(["a", "b"], {"a"}) == 1.0

    def test_third_position_hit(self):
        assert reciprocal_rank(["x", "y", "a"], {"a"}) == pytest_approx(1 / 3)

    def test_no_hit_is_zero(self):
        assert reciprocal_rank(["x", "y"], {"a"}) == 0.0


class TestAggregation:
    def test_aggregate_averages_across_jobs(self):
        job1 = evaluate_single_job(["a", "b"], {"a", "b"})
        job2 = evaluate_single_job(["x", "y"], {"z"})  # zero relevant found
        agg = aggregate_metrics([job1, job2])
        assert agg["precision_at_5"] == pytest_approx((job1["precision_at_5"] + job2["precision_at_5"]) / 2)

    def test_empty_list_returns_zeros(self):
        agg = aggregate_metrics([])
        assert agg == {"precision_at_5": 0.0, "precision_at_10": 0.0, "ndcg_at_10": 0.0, "mrr": 0.0}


class TestRegressionCheck:
    def test_improved_metrics_promote(self):
        baseline = {"precision_at_5": 0.8, "precision_at_10": 0.7, "ndcg_at_10": 0.75, "mrr": 0.8}
        new = {"precision_at_5": 0.85, "precision_at_10": 0.72, "ndcg_at_10": 0.78, "mrr": 0.82}
        assert should_promote_weights(new, baseline) is True

    def test_small_drop_within_tolerance_promotes(self):
        baseline = {"precision_at_5": 0.8, "precision_at_10": 0.7, "ndcg_at_10": 0.75, "mrr": 0.8}
        new = {"precision_at_5": 0.79, "precision_at_10": 0.7, "ndcg_at_10": 0.75, "mrr": 0.8}  # -1.25%
        assert should_promote_weights(new, baseline) is True

    def test_large_drop_beyond_tolerance_rolls_back(self):
        baseline = {"precision_at_5": 0.8, "precision_at_10": 0.7, "ndcg_at_10": 0.75, "mrr": 0.8}
        new = {"precision_at_5": 0.7, "precision_at_10": 0.7, "ndcg_at_10": 0.75, "mrr": 0.8}  # -12.5%, > 5% tolerance
        assert should_promote_weights(new, baseline) is False
