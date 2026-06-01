"""In-memory implementation of the Store contract, for fast tests.

Mirrors SqliteStore's behaviour without a database, so the same behaviour suite
runs against both and proves they are interchangeable behind the protocol.
"""

from __future__ import annotations

from odr.types import Chunk, Document, Filters, IngestRun, ScoredChunk, SourceMeta


class InMemoryStore:
    def __init__(self) -> None:
        self._documents: dict[str, Document] = {}
        self._chunks: dict[str, list[Chunk]] = {}
        self._ingest_runs: list[IngestRun] = []
        self._vectors: dict[str, list[float]] = {}
        self._sources: dict[str, SourceMeta] = {}

    def init_schema(self) -> None:
        return None

    def upsert_source(self, meta: SourceMeta) -> None:
        self._sources[meta.id] = meta

    def get_source(self, source_id: str) -> SourceMeta | None:
        return self._sources.get(source_id)

    def upsert_document(self, doc: Document) -> str:
        doc_id = f"{doc.source_id}:{doc.source_ref}"
        self._documents[doc_id] = doc
        return doc_id

    def content_hash_exists(self, content_hash: str) -> bool:
        return any(d.content_hash == content_hash for d in self._documents.values())

    def document_exists(self, source_id: str, source_ref: str) -> bool:
        return f"{source_id}:{source_ref}" in self._documents

    def document_count(self) -> int:
        return len(self._documents)

    def upsert_chunks(
        self,
        document_id: str,
        chunks: list[Chunk],
        vectors: list[list[float]] | None = None,
        model_id: str | None = None,
    ) -> None:
        if vectors is not None and len(vectors) != len(chunks):
            raise ValueError("vectors length must match chunks length")
        self._chunks[document_id] = list(chunks)
        for cid in [c for c in self._vectors if c.startswith(f"{document_id}#")]:
            del self._vectors[cid]
        if vectors is not None:
            for c, v in zip(chunks, vectors, strict=True):
                self._vectors[f"{document_id}#{c.ordinal}"] = list(v)

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
        # Brute-force L2 over stored vectors — same metric/scoring as SqliteStore.
        scored: list[tuple[float, str, str, str, Document | None]] = []
        for document_id, chunks in self._chunks.items():
            doc = self._documents.get(document_id)
            for c in chunks:
                chunk_id = f"{document_id}#{c.ordinal}"
                vec = self._vectors.get(chunk_id)
                if vec is None:
                    continue
                dist = sum((a - b) ** 2 for a, b in zip(query_vec, vec, strict=True)) ** 0.5
                scored.append((dist, chunk_id, document_id, c.text, doc))
        scored.sort(key=lambda r: r[0])
        return [
            ScoredChunk(
                chunk_id=chunk_id,
                document_id=document_id,
                title=doc.title if doc else "",
                text=text,
                score=1.0 / (1.0 + dist),
                source_name=doc.source_id if doc else "",
                url=doc.url if doc else "",
                published_at=doc.published_at if doc else None,
            )
            for dist, chunk_id, document_id, text, doc in scored[:k]
        ]

    def keyword_search(
        self, query: str, k: int, filters: Filters | None = None
    ) -> list[ScoredChunk]:
        raise NotImplementedError("keyword_search lands in #19 (FTS5)")
