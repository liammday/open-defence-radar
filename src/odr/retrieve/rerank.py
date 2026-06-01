"""Optional cross-encoder reranker — OFF by default (ODR_RERANK).

A cross-encoder scores each (query, passage) pair directly, which is more
accurate than fusion but slower and needs a model. Whether it actually beats RRF
is a question for the Phase 2 eval harness, so it is opt-in until proven.
"""

from __future__ import annotations

import os
from dataclasses import replace
from typing import Any, Protocol

from odr.types import ScoredChunk


class Reranker(Protocol):
    model_id: str

    def rerank(self, query: str, chunks: list[ScoredChunk]) -> list[ScoredChunk]: ...


class LocalReranker:
    """fastembed cross-encoder (BGE reranker). Loads lazily on first use."""

    model_id = "BAAI/bge-reranker-base"

    def __init__(self) -> None:
        self._model: Any | None = None

    def _ensure_model(self) -> Any:
        if self._model is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            self._model = TextCrossEncoder(model_name=self.model_id)
        return self._model

    def rerank(self, query: str, chunks: list[ScoredChunk]) -> list[ScoredChunk]:
        if not chunks:
            return chunks
        scores = list(self._ensure_model().rerank(query, [c.text for c in chunks]))
        ordered = sorted(zip(chunks, scores, strict=True), key=lambda cs: cs[1], reverse=True)
        return [replace(chunk, score=float(score)) for chunk, score in ordered]


def get_reranker() -> Reranker | None:
    if os.environ.get("ODR_RERANK", "0").lower() in ("1", "true", "on", "yes"):
        return LocalReranker()
    return None
