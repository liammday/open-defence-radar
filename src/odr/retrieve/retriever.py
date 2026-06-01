"""Semantic retriever — the clean seam the synthesiser and MCP tool call.

Phase 0: embed the query and return the store's nearest passages. Hybrid
(keyword + RRF fusion) and filters arrive in Phase 1 (#19-#21).
"""

from __future__ import annotations

from odr.embed.base import Embedder
from odr.store.base import Store
from odr.types import Filters, ScoredChunk


class Retriever:
    def __init__(self, store: Store, embedder: Embedder) -> None:
        self._store = store
        self._embedder = embedder

    def retrieve(self, query: str, k: int = 8, filters: Filters | None = None) -> list[ScoredChunk]:
        query_vec = self._embedder.embed([query])[0]
        return self._store.semantic_search(query_vec, k, filters)
