"""The Store contract — the seam between the pipeline and persistence.

Coding to this protocol (rather than a concrete class) is what lets v0's
single-file SQLite + sqlite-vec store be swapped for Postgres + pgvector later
without touching callers. Vector + keyword search land in #10 / #19.
"""

from __future__ import annotations

from typing import Protocol

from odr.types import Chunk, Document, Filters, IngestRun, ScoredChunk, SourceMeta


class Store(Protocol):
    def init_schema(self) -> None:
        """Create tables/indexes if absent. Idempotent."""
        ...

    def upsert_source(self, meta: SourceMeta) -> None:
        """Record an open source's provenance (licence, access method)."""
        ...

    def get_source(self, source_id: str) -> SourceMeta | None: ...

    def upsert_document(self, doc: Document) -> str:
        """Insert or update a document by (source_id, source_ref); return its id."""
        ...

    def content_hash_exists(self, content_hash: str) -> bool:
        """True if any stored document has this content hash (exact dedupe)."""
        ...

    def document_count(self) -> int: ...

    def upsert_chunks(
        self,
        document_id: str,
        chunks: list[Chunk],
        vectors: list[list[float]] | None = None,
        model_id: str | None = None,
    ) -> None:
        """Replace a document's chunks. Vectors are wired in #10 (sqlite-vec)."""
        ...

    def chunk_count(self, document_id: str | None = None) -> int: ...

    def record_ingest_run(self, run: IngestRun) -> int:
        """Persist an ingest-run log row; return its id."""
        ...

    def ingest_run_count(self) -> int: ...

    def semantic_search(
        self, query_vec: list[float], k: int, filters: Filters | None = None
    ) -> list[ScoredChunk]:
        """Vector KNN search. Lands in #10 (sqlite-vec)."""
        ...

    def keyword_search(
        self, query: str, k: int, filters: Filters | None = None
    ) -> list[ScoredChunk]:
        """BM25 keyword search. Lands in #19 (FTS5)."""
        ...
