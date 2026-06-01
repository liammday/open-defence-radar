"""Core domain types — the shapes data takes as it flows through the pipeline.

All frozen (immutable value objects). The relational/vector stores persist these;
the retriever and synthesiser consume and produce them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class Document:
    """A single ingested open-source record, normalised to the common schema."""

    source_id: str
    source_ref: str  # the source's own id (e.g. an OCDS OCID)
    title: str
    url: str
    text: str
    content_hash: str  # for dedupe
    published_at: date | None = None
    raw: dict | None = None  # the original payload, kept for provenance/debug


@dataclass(frozen=True)
class Chunk:
    """A retrievable slice of a document's text."""

    document_id: str
    ordinal: int
    text: str
    token_count: int


@dataclass(frozen=True)
class ScoredChunk:
    """A chunk returned by retrieval, with its score and joined provenance."""

    chunk_id: str
    document_id: str
    text: str
    score: float
    source_name: str
    url: str
    published_at: date | None = None


@dataclass(frozen=True)
class Citation:
    """A resolved citation marker pointing back to a retrieved passage."""

    marker: str
    chunk_id: str
    document_title: str
    source_name: str
    url: str
    published_at: date | None = None


@dataclass(frozen=True)
class Filters:
    """Optional retrieval filters (Phase 1)."""

    date_from: date | None = None
    date_to: date | None = None
    sources: tuple[str, ...] | None = None


@dataclass(frozen=True)
class GroundednessReport:
    """How well an answer's claims are supported by retrieved passages."""

    total_claims: int
    supported: int
    unsupported: int

    @property
    def score(self) -> float:
        return self.supported / self.total_claims if self.total_claims else 1.0


@dataclass(frozen=True)
class Answer:
    """A grounded answer: cited text plus its provenance and groundedness read."""

    text: str
    citations: tuple[Citation, ...]
    groundedness: GroundednessReport
    retrieved: tuple[ScoredChunk, ...]


@dataclass(frozen=True)
class IngestRun:
    """A record of one ingest job, for the ingest log."""

    source_id: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    docs_seen: int
    docs_new: int
    docs_updated: int
    error: str | None = None


@dataclass(frozen=True)
class SourceMeta:
    """Provenance metadata for an open source (the `source` table row)."""

    id: str
    name: str
    url: str
    access_method: str
    licence: str
    attribution: str | None = None
    enabled: bool = True
