"""Retrieval-quality scorers — pure functions over (relevant, retrieved) ids.

Aggregated across the question set by `score_retrieval`. No LLM; groundedness
(which does use a judge) lives in the groundedness module.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


def hit_rate(relevant: Sequence[str], retrieved: Sequence[str]) -> float:
    """1.0 if any relevant id is in the retrieved set, else 0.0."""
    return 1.0 if set(relevant) & set(retrieved) else 0.0


def recall_at_k(relevant: Sequence[str], retrieved: Sequence[str]) -> float:
    """Fraction of relevant ids that appear in the retrieved set."""
    if not relevant:
        return 1.0
    return len(set(relevant) & set(retrieved)) / len(set(relevant))


def reciprocal_rank(relevant: Sequence[str], retrieved: Sequence[str]) -> float:
    """1 / rank of the first relevant id (0.0 if none retrieved)."""
    rel = set(relevant)
    for rank, doc_id in enumerate(retrieved, start=1):
        if doc_id in rel:
            return 1.0 / rank
    return 0.0


@dataclass(frozen=True)
class RetrievalScores:
    hit_rate: float
    recall_at_k: float
    mrr: float


def score_retrieval(pairs: Sequence[tuple[Sequence[str], Sequence[str]]]) -> RetrievalScores:
    """Mean hit-rate / recall@k / MRR across (relevant, retrieved) pairs."""
    if not pairs:
        return RetrievalScores(0.0, 0.0, 0.0)
    n = len(pairs)
    return RetrievalScores(
        hit_rate=sum(hit_rate(r, g) for r, g in pairs) / n,
        recall_at_k=sum(recall_at_k(r, g) for r, g in pairs) / n,
        mrr=sum(reciprocal_rank(r, g) for r, g in pairs) / n,
    )
