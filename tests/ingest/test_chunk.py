"""Chunker protocol + WholeRecordChunker (for short structured records)."""

from __future__ import annotations

from odr.ingest.chunk import Chunker, WholeRecordChunker, WindowChunker
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


def test_window_chunker_conforms_to_protocol() -> None:
    _requires_chunker(WindowChunker())


def test_window_chunker_single_chunk_for_short_text() -> None:
    chunks = WindowChunker(window=10, overlap=2).chunk("d", _doc("one two three"))
    assert len(chunks) == 1
    assert chunks[0].text == "one two three"
    assert chunks[0].token_count == 3


def test_window_chunker_splits_long_text_with_overlap() -> None:
    text = " ".join(f"w{i}" for i in range(25))  # 25 words
    chunks = WindowChunker(window=10, overlap=2).chunk("d", _doc(text))
    assert len(chunks) == 3
    assert [c.ordinal for c in chunks] == [0, 1, 2]
    assert all(c.token_count <= 10 for c in chunks)
    # consecutive windows overlap by `overlap` words
    assert chunks[0].text.split()[-2:] == chunks[1].text.split()[:2]
    # the windows cover through the final word
    assert chunks[-1].text.split()[-1] == "w24"


def test_window_chunker_skips_empty_text() -> None:
    assert WindowChunker().chunk("d", _doc("   ")) == []
