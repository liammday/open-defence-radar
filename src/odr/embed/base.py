"""The Embedder contract — a swappable text→vector provider.

LocalEmbedder (default, offline) and FakeEmbedder (tests) implement it; hosted
providers (Voyage/OpenAI) can be added behind the same protocol later.
"""

from __future__ import annotations

from typing import Protocol


class Embedder(Protocol):
    model_id: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts into vectors of length ``dim``."""
        ...
