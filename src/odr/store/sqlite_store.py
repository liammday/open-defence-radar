"""SQLite implementation of the Store contract (relational parts).

For v0 the whole knowledge base is one SQLite file. Vector search (#10, via the
sqlite-vec extension) and keyword search (#19, via FTS5) live in the same file
and are added to this class in those issues.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from odr.types import Chunk, Document, Filters, IngestRun, ScoredChunk

_SCHEMA = """
CREATE TABLE IF NOT EXISTS source (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    url           TEXT,
    access_method TEXT,
    licence       TEXT,
    attribution   TEXT,
    enabled       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS document (
    id           TEXT PRIMARY KEY,
    source_id    TEXT NOT NULL,
    source_ref   TEXT NOT NULL,
    title        TEXT,
    url          TEXT,
    published_at TEXT,
    fetched_at   TEXT,
    content_hash TEXT NOT NULL,
    text         TEXT NOT NULL,
    raw          TEXT,
    UNIQUE (source_id, source_ref)
);
CREATE INDEX IF NOT EXISTS idx_document_content_hash ON document (content_hash);
CREATE INDEX IF NOT EXISTS idx_document_published_at ON document (published_at);

CREATE TABLE IF NOT EXISTS chunk (
    id              TEXT PRIMARY KEY,
    document_id     TEXT NOT NULL REFERENCES document (id) ON DELETE CASCADE,
    ordinal         INTEGER NOT NULL,
    text            TEXT NOT NULL,
    token_count     INTEGER NOT NULL,
    embedding_model TEXT,
    UNIQUE (document_id, ordinal)
);
CREATE INDEX IF NOT EXISTS idx_chunk_document ON chunk (document_id);

CREATE TABLE IF NOT EXISTS ingest_run (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id    TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    status       TEXT NOT NULL,
    docs_seen    INTEGER NOT NULL DEFAULT 0,
    docs_new     INTEGER NOT NULL DEFAULT 0,
    docs_updated INTEGER NOT NULL DEFAULT 0,
    error        TEXT
);
"""


class SqliteStore:
    def __init__(self, db_path: str | Path) -> None:
        self.path = str(db_path)
        self._conn = sqlite3.connect(self.path)
        self._conn.execute("PRAGMA foreign_keys = ON")
        # WAL persists in the file header; no-op for :memory:.
        self._conn.execute("PRAGMA journal_mode = WAL")

    def init_schema(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def upsert_document(self, doc: Document) -> str:
        doc_id = f"{doc.source_id}:{doc.source_ref}"
        self._conn.execute(
            """
            INSERT INTO document
                (id, source_id, source_ref, title, url, published_at, content_hash, text, raw)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (source_id, source_ref) DO UPDATE SET
                title=excluded.title, url=excluded.url, published_at=excluded.published_at,
                content_hash=excluded.content_hash, text=excluded.text, raw=excluded.raw
            """,
            (
                doc_id,
                doc.source_id,
                doc.source_ref,
                doc.title,
                doc.url,
                doc.published_at.isoformat() if doc.published_at else None,
                doc.content_hash,
                doc.text,
                json.dumps(doc.raw) if doc.raw is not None else None,
            ),
        )
        self._conn.commit()
        return doc_id

    def content_hash_exists(self, content_hash: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM document WHERE content_hash = ? LIMIT 1", (content_hash,)
        ).fetchone()
        return row is not None

    def document_count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM document").fetchone()[0])

    def upsert_chunks(
        self,
        document_id: str,
        chunks: list[Chunk],
        vectors: list[list[float]] | None = None,
        model_id: str | None = None,
    ) -> None:
        # Replace semantics: a document's chunks are rewritten wholesale.
        # TODO(odr): persist `vectors` into the sqlite-vec table in #10.
        self._conn.execute("DELETE FROM chunk WHERE document_id = ?", (document_id,))
        self._conn.executemany(
            """
            INSERT INTO chunk (id, document_id, ordinal, text, token_count, embedding_model)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    f"{document_id}#{c.ordinal}",
                    document_id,
                    c.ordinal,
                    c.text,
                    c.token_count,
                    model_id,
                )
                for c in chunks
            ],
        )
        self._conn.commit()

    def chunk_count(self, document_id: str | None = None) -> int:
        if document_id is None:
            row = self._conn.execute("SELECT COUNT(*) FROM chunk").fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM chunk WHERE document_id = ?", (document_id,)
            ).fetchone()
        return int(row[0])

    def record_ingest_run(self, run: IngestRun) -> int:
        cur = self._conn.execute(
            """
            INSERT INTO ingest_run
            (source_id, started_at, finished_at, status, docs_seen, docs_new, docs_updated, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.source_id,
                run.started_at.isoformat(),
                run.finished_at.isoformat() if run.finished_at else None,
                run.status,
                run.docs_seen,
                run.docs_new,
                run.docs_updated,
                run.error,
            ),
        )
        self._conn.commit()
        rowid = cur.lastrowid
        assert rowid is not None
        return rowid

    def ingest_run_count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM ingest_run").fetchone()[0])

    def semantic_search(
        self, query_vec: list[float], k: int, filters: Filters | None = None
    ) -> list[ScoredChunk]:
        # TODO(odr): implement via sqlite-vec in #10.
        raise NotImplementedError("semantic_search lands in #10 (sqlite-vec)")

    def keyword_search(
        self, query: str, k: int, filters: Filters | None = None
    ) -> list[ScoredChunk]:
        # TODO(odr): implement via FTS5 in #19.
        raise NotImplementedError("keyword_search lands in #19 (FTS5)")
