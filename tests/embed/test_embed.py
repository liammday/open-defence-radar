"""Embedder protocol, factory, and the deterministic FakeEmbedder.

The real LocalEmbedder downloads a model on first use, so it is NOT exercised
here (verified by a spike against the real model); the suite uses FakeEmbedder.
"""

from __future__ import annotations

import pytest

from odr.embed.base import Embedder
from odr.embed.factory import get_embedder
from odr.embed.fake import FakeEmbedder
from odr.embed.local import LocalEmbedder


def _requires_embedder(_e: Embedder) -> None:
    """No-op whose signature makes mypy enforce Embedder conformance."""


def test_embedders_conform_to_protocol() -> None:
    _requires_embedder(FakeEmbedder())
    _requires_embedder(LocalEmbedder())  # cheap: model loads lazily, not here


def test_fake_embedder_is_deterministic_and_right_dim() -> None:
    embedder = FakeEmbedder(dim=8)
    first = embedder.embed(["hello", "world"])
    second = embedder.embed(["hello", "world"])
    assert len(first) == 2
    assert len(first[0]) == 8
    assert first == second  # deterministic
    assert embedder.embed(["hello"])[0] == first[0]  # per-text stable


def test_fake_embedder_handles_empty_batch() -> None:
    assert FakeEmbedder().embed([]) == []


def test_factory_defaults_to_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ODR_EMBEDDER", raising=False)
    assert isinstance(get_embedder(), LocalEmbedder)
    assert get_embedder("local").model_id == "BAAI/bge-small-en-v1.5"
    assert get_embedder("local").dim == 384


def test_factory_fake_and_unknown() -> None:
    assert isinstance(get_embedder("fake"), FakeEmbedder)
    with pytest.raises(ValueError, match="embedder"):
        get_embedder("nope")
