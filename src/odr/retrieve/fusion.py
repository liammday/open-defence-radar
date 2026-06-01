"""Reciprocal Rank Fusion — combine ranked lists deterministically (no model).

score(d) = Σ_i 1 / (rrf_k + rank_i(d)) over each ranking the chunk appears in.
A chunk near the top of multiple rankings beats one near the top of just one.
"""

from __future__ import annotations

from dataclasses import replace

from odr.types import ScoredChunk


def reciprocal_rank_fusion(
    rankings: list[list[ScoredChunk]], k: int, rrf_k: int = 60
) -> list[ScoredChunk]:
    scores: dict[str, float] = {}
    representative: dict[str, ScoredChunk] = {}
    for ranking in rankings:
        for rank, chunk in enumerate(ranking, start=1):
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (rrf_k + rank)
            representative.setdefault(chunk.chunk_id, chunk)
    ordered = sorted(representative.values(), key=lambda c: scores[c.chunk_id], reverse=True)
    return [replace(chunk, score=scores[chunk.chunk_id]) for chunk in ordered[:k]]
