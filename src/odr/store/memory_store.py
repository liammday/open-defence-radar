"""In-memory implementation of the Store contract, for fast tests.

Mirrors SqliteStore's behaviour without a database, so the same behaviour suite
runs against both and proves they are interchangeable behind the protocol.
"""

from __future__ import annotations

from odr.types import Chunk, Document, Filters, IngestRun, ScoredChunk


class InMemoryStore:
    def __init__(self) -> None:
        self._documents: dict[str, Document] = {}
        self._chunks: dict[str, list[Chunk]] = {}
        self._ingest_runs: list[IngestRun] = []

    def init_schema(self) -> None:
        return None

    def upsert_document(self, doc: Document) -> str:
        doc_id = f"{doc.source_id}:{doc.source_ref}"
        self._documents[doc_id] = doc
        return doc_id

    def content_hash_exists(self, content_hash: str) -> bool:
        return any(d.content_hash == content_hash for d in self._documents.values())

    def document_count(self) -> int:
        return len(self._documents)

    def upsert_chunks(
        self,
        document_id: str,
        chunks: list[Chunk],
        vectors: list[list[float]] | None = None,
        model_id: str | None = None,
    ) -> None:
        self._chunks[document_id] = list(chunks)

    def chunk_count(self, document_id: str | None = None) -> int:
        if document_id is None:
            return sum(len(v) for v in self._chunks.values())
        return len(self._chunks.get(document_id, []))

    def record_ingest_run(self, run: IngestRun) -> int:
        self._ingest_runs.append(run)
        return len(self._ingest_runs)

    def ingest_run_count(self) -> int:
        return len(self._ingest_runs)

    def semantic_search(
        self, query_vec: list[float], k: int, filters: Filters | None = None
    ) -> list[ScoredChunk]:
        raise NotImplementedError("semantic_search lands in #10 (sqlite-vec)")

    def keyword_search(
        self, query: str, k: int, filters: Filters | None = None
    ) -> list[ScoredChunk]:
        raise NotImplementedError("keyword_search lands in #19 (FTS5)")
