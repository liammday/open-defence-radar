"""Chunker protocol + WholeRecordChunker (for short structured records)."""

from __future__ import annotations

from odr.ingest.chunk import Chunker, WholeRecordChunker
from odr.types import Document


def _requires_chunker(_c: Chunker) -> None:
    """No-op whose signature makes mypy enforce Chunker conformance."""


def _doc(text: str) -> Document:
    return Document(
        source_id="contracts-finder",
        source_ref="r1",
        title="t",
        url="u",
        text=text,
        content_hash="h",
    )


def test_chunker_conforms_to_protocol() -> None:
    _requires_chunker(WholeRecordChunker())


def test_whole_record_chunker_yields_one_chunk() -> None:
    chunks = WholeRecordChunker().chunk("contracts-finder:r1", _doc("hello world foo"))
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.document_id == "contracts-finder:r1"
    assert chunk.ordinal == 0
    assert chunk.text == "hello world foo"
    assert chunk.token_count == 3


def test_whole_record_chunker_skips_empty_text() -> None:
    assert WholeRecordChunker().chunk("contracts-finder:r1", _doc("   ")) == []
