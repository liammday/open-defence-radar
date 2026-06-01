"""Embedder selection — `ODR_EMBEDDER` (default: local)."""

from __future__ import annotations

import os

from odr.embed.base import Embedder
from odr.embed.fake import FakeEmbedder
from odr.embed.local import LocalEmbedder


def get_embedder(name: str | None = None) -> Embedder:
    name = (name or os.environ.get("ODR_EMBEDDER") or "local").lower()
    if name == "local":
        return LocalEmbedder()
    if name == "fake":
        return FakeEmbedder()
    raise ValueError(f"Unknown embedder {name!r} (expected 'local' or 'fake')")
