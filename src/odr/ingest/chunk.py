"""Chunking strategies — split a Document's text into retrievable Chunks.

WholeRecordChunker suits short, structured records (e.g. OCDS procurement
notices), which are best kept as a single chunk. The windowed chunker for long
prose (GOV.UK/MoD news) arrives in #23.
"""

from __future__ import annotations

from typing import Protocol

from odr.types import Chunk, Document


class Chunker(Protocol):
    def chunk(self, document_id: str, doc: Document) -> list[Chunk]: ...


class WholeRecordChunker:
    """One chunk per document, preserving the normalised record as-is."""

    def chunk(self, document_id: str, doc: Document) -> list[Chunk]:
        text = doc.text.strip()
        if not text:
            return []
        return [
            Chunk(
                document_id=document_id,
                ordinal=0,
                text=text,
                token_count=len(text.split()),
            )
        ]


class WindowChunker:
    """Sliding word-windows with overlap — for long prose (e.g. GOV.UK news).

    Word-based as a v0 proxy for tokens; `token_count` is the word count.
    """

    def __init__(self, window: int = 200, overlap: int = 40) -> None:
        if not 0 <= overlap < window:
            raise ValueError("overlap must be >= 0 and < window")
        self.window = window
        self.overlap = overlap

    def chunk(self, document_id: str, doc: Document) -> list[Chunk]:
        words = doc.text.split()
        if not words:
            return []
        step = self.window - self.overlap
        chunks: list[Chunk] = []
        start = 0
        ordinal = 0
        while start < len(words):
            window_words = words[start : start + self.window]
            chunks.append(
                Chunk(
                    document_id=document_id,
                    ordinal=ordinal,
                    text=" ".join(window_words),
                    token_count=len(window_words),
                )
            )
            if start + self.window >= len(words):
                break
            start += step
            ordinal += 1
        return chunks
