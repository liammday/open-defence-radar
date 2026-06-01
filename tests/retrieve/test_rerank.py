"""Reranker protocol + factory. Off by default; adoption is an eval (Phase 2) call.

The real cross-encoder downloads a model, so it is not exercised here (mirrors
the embedder); the Retriever-integration test uses a trivial reorderer.
"""

from __future__ import annotations

import pytest

from odr.retrieve.rerank import LocalReranker, Reranker, get_reranker


def _requires_reranker(_r: Reranker) -> None:
    """No-op whose signature makes mypy enforce Reranker conformance."""


def test_local_reranker_conforms_to_protocol() -> None:
    _requires_reranker(LocalReranker())  # cheap: model loads lazily, not here


def test_get_reranker_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ODR_RERANK", raising=False)
    assert get_reranker() is None


def test_get_reranker_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ODR_RERANK", "1")
    assert isinstance(get_reranker(), LocalReranker)
