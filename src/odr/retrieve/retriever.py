"""Hybrid retriever — the clean seam the synthesiser and MCP tool call.

Fuses semantic (vector) and keyword (BM25) rankings via Reciprocal Rank Fusion.
Each backend is over-fetched to a pool, then fused down to the top k. Date/source
filters arrive in #21; an eval-gated reranker in #25.
"""

from __future__ import annotations

from odr.embed.base import Embedder
from odr.retrieve.fusion import reciprocal_rank_fusion
from odr.store.base import Store
from odr.types import Filters, ScoredChunk


class Retriever:
    def __init__(self, store: Store, embedder: Embedder) -> None:
        self._store = store
        self._embedder = embedder

    def retrieve(self, query: str, k: int = 8, filters: Filters | None = None) -> list[ScoredChunk]:
        pool = max(k, 20)
        semantic = self._store.semantic_search(self._embedder.embed([query])[0], pool, filters)
        keyword = self._store.keyword_search(query, pool, filters)
        return reciprocal_rank_fusion([semantic, keyword], k)
