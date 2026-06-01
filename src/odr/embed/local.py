"""Local, offline embedder using fastembed (ONNX BGE-small).

Default provider: runs from a clean clone with no API key or cost. The model
(~130 MB) downloads once on first use and is cached; loading is lazy so importing
this module (and constructing the embedder) stays cheap.
"""

from __future__ import annotations

from typing import Any


class LocalEmbedder:
    model_id = "BAAI/bge-small-en-v1.5"
    dim = 384

    def __init__(self) -> None:
        self._model: Any | None = None

    def _ensure_model(self) -> Any:
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(model_name=self.model_id)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._ensure_model()
        return [[float(x) for x in vec] for vec in model.embed(texts)]
