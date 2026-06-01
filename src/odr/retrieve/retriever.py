"""Hybrid retriever — the clean seam the synthesiser and MCP tool call.

Fuses semantic (vector) and keyword (BM25) rankings via Reciprocal Rank Fusion,
then optionally reranks with a cross-encoder (off by default). Each backend is
over-fetched to a pool; the pool is fused/reranked, then sliced to the top k.
"""

from __future__ import annotations

from odr.embed.base import Embedder
from odr.retrieve.fusion import reciprocal_rank_fusion
from odr.retrieve.rerank import Reranker
from odr.store.base import Store
from odr.types import Filters, ScoredChunk


class Retriever:
    def __init__(self, store: Store, embedder: Embedder, reranker: Reranker | None = None) -> None:
        self._store = store
        self._embedder = embedder
        self._reranker = reranker

    def retrieve(self, query: str, k: int = 8, filters: Filters | None = None) -> list[ScoredChunk]:
        pool = max(k, 20)
        semantic = self._store.semantic_search(self._embedder.embed([query])[0], pool, filters)
        keyword = self._store.keyword_search(query, pool, filters)
        fused = reciprocal_rank_fusion([semantic, keyword], pool)
        if self._reranker is not None:
            fused = self._reranker.rerank(query, fused)
        return fused[:k]
