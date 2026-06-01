"""Reciprocal Rank Fusion of multiple ranked lists."""

from __future__ import annotations

from odr.retrieve.fusion import reciprocal_rank_fusion
from odr.types import ScoredChunk


def _sc(chunk_id: str) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=chunk_id,
        document_id="d",
        title="t",
        text=chunk_id,
        score=0.0,
        source_name="s",
        url="u",
    )


def test_rrf_rewards_appearing_in_both_lists() -> None:
    semantic = [_sc("x"), _sc("y")]  # x@1, y@2
    keyword = [_sc("y"), _sc("z")]  # y@1, z@2
    fused = reciprocal_rank_fusion([semantic, keyword], k=3)
    ids = [c.chunk_id for c in fused]
    assert ids[0] == "y"  # appears in both -> highest fused score
    assert set(ids) == {"x", "y", "z"}  # de-duplicated union
    assert fused[0].score >= fused[1].score  # fused score is attached, descending


def test_rrf_respects_k() -> None:
    only = [_sc("x"), _sc("y"), _sc("z")]
    assert len(reciprocal_rank_fusion([only], k=2)) == 2


def test_rrf_empty() -> None:
    assert reciprocal_rank_fusion([[], []], k=5) == []
