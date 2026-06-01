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
