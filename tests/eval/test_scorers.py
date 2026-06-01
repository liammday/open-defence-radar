"""Retrieval-quality scorers (pure; no LLM)."""

from __future__ import annotations

from odr.eval.scorers import hit_rate, recall_at_k, reciprocal_rank, score_retrieval


def test_hit_rate() -> None:
    assert hit_rate(["a"], ["x", "a", "y"]) == 1.0
    assert hit_rate(["a"], ["x", "y"]) == 0.0


def test_recall_at_k() -> None:
    assert recall_at_k(["a", "b"], ["a", "x"]) == 0.5
    assert recall_at_k(["a", "b"], ["a", "b", "c"]) == 1.0
    assert recall_at_k([], ["x"]) == 1.0  # nothing to recall


def test_reciprocal_rank() -> None:
    assert reciprocal_rank(["a"], ["a", "b"]) == 1.0
    assert reciprocal_rank(["b"], ["a", "b"]) == 0.5
    assert reciprocal_rank(["z"], ["a", "b"]) == 0.0


def test_score_retrieval_aggregates_means() -> None:
    pairs = [(["a"], ["a", "x"]), (["b"], ["x", "y"])]  # one hit, one miss
    scores = score_retrieval(pairs)
    assert scores.hit_rate == 0.5
    assert scores.mrr == 0.5  # (1.0 + 0.0) / 2
    assert score_retrieval([]).hit_rate == 0.0
