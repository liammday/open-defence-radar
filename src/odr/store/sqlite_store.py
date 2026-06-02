"""SQLite implementation of the Store contract, using apsw + sqlite-vec.

We use **apsw** rather than the stdlib ``sqlite3`` because loading SQLite
extensions — required for sqlite-vec's vector index — needs a SQLite build with
loadable extensions enabled, which the stdlib ``sqlite3`` on several platforms
(including the python.org macOS builds) does NOT provide. apsw bundles a modern
SQLite with extension loading and ships cross-platform wheels. The whole
knowledge base is still one SQLite file.

Keyword search (FTS5) lands in #19; retrieval filters in #21.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

import apsw
import sqlite_vec

from odr.types import (
    Chunk,
    Document,
    Filters,
    IngestRun,
    RegionStat,
    ScoredChunk,
    SourceMeta,
    SourceStat,
)

DEFAULT_DIM = 384  # BGE-small-en-v1.5; the local-embedder default arrives in #12.

_RELATIONAL_SCHEMA = """
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
    region_code  TEXT,
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


def _open_connection(path: str) -> apsw.Connection:
    """Open a connection with the sqlite-vec extension loaded and WAL enabled."""
    con = apsw.Connection(path)
    try:
        con.enableloadextension(True)
        con.loadextension(sqlite_vec.loadable_path())
    except apsw.Error as exc:  # pragma: no cover - defensive
        raise RuntimeError(
            "Could not load the sqlite-vec extension. The pinned apsw build should "
            "support loadable extensions; check the install."
        ) from exc
    finally:
        con.enableloadextension(False)
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


class SqliteStore:
    def __init__(self, db_path: str | Path, dim: int = DEFAULT_DIM) -> None:
        self.path = str(db_path)
        self.dim = dim
        self._conn = _open_connection(self.path)

    def init_schema(self) -> None:
        self._conn.execute(_RELATIONAL_SCHEMA)
        # Additive migration: pre-Phase-5 stores predate the region_code column.
        # Add it (and its index) before anything reads/indexes it.
        self._ensure_column("document", "region_code", "TEXT")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_document_region ON document (region_code)"
        )
        self._conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS chunk_vec "
            f"USING vec0(chunk_id TEXT PRIMARY KEY, embedding float[{self.dim}])"
        )
        self._conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(chunk_id UNINDEXED, text)"
        )

    def _ensure_column(self, table: str, column: str, decl: str) -> None:
        """Add `column` to `table` if absent — an idempotent additive migration."""
        cols = {r[1] for r in self._conn.execute(f"PRAGMA table_info({table})")}
        if column not in cols:
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

    def upsert_source(self, meta: SourceMeta) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO source (id, name, url, access_method, licence, attribution, enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET
                    name=excluded.name, url=excluded.url,
                    access_method=excluded.access_method, licence=excluded.licence,
                    attribution=excluded.attribution, enabled=excluded.enabled
                """,
                (
                    meta.id,
                    meta.name,
                    meta.url,
                    meta.access_method,
                    meta.licence,
                    meta.attribution,
                    int(meta.enabled),
                ),
            )

    def get_source(self, source_id: str) -> SourceMeta | None:
        rows = list(
            self._conn.execute(
                "SELECT id, name, url, access_method, licence, attribution, enabled "
                "FROM source WHERE id = ?",
                (source_id,),
            )
        )
        if not rows:
            return None
        r = rows[0]
        return SourceMeta(
            id=r[0],
            name=r[1],
            url=r[2],
            access_method=r[3],
            licence=r[4],
            attribution=r[5],
            enabled=bool(r[6]),
        )

    def upsert_document(self, doc: Document) -> str:
        doc_id = f"{doc.source_id}:{doc.source_ref}"
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO document
                    (id, source_id, source_ref, title, url, published_at, content_hash,
                     text, raw, region_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (source_id, source_ref) DO UPDATE SET
                    title=excluded.title, url=excluded.url, published_at=excluded.published_at,
                    content_hash=excluded.content_hash, text=excluded.text, raw=excluded.raw,
                    region_code=excluded.region_code
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
                    doc.region_code,
                ),
            )
        return doc_id

    def backfill_region_codes(self, derive: Callable[[str | None], str | None]) -> int:
        """Re-derive region_code for every stored document from its retained raw.

        `derive` maps a document's stored raw JSON (or None) to an ITL-1 code (or
        None). Used by `odr geo backfill` so a pre-Phase-5 corpus gains regions
        without re-fetching. Returns the number of rows whose code changed.
        """
        rows = list(self._conn.execute("SELECT id, raw, region_code FROM document"))
        changed = 0
        with self._conn:
            for doc_id, raw, current in rows:
                new = derive(raw)
                if new != current:
                    self._conn.execute(
                        "UPDATE document SET region_code = ? WHERE id = ?", (new, doc_id)
                    )
                    changed += 1
        return changed

    def content_hash_exists(self, content_hash: str) -> bool:
        rows = list(
            self._conn.execute(
                "SELECT 1 FROM document WHERE content_hash = ? LIMIT 1", (content_hash,)
            )
        )
        return len(rows) > 0

    def document_exists(self, source_id: str, source_ref: str) -> bool:
        rows = list(
            self._conn.execute(
                "SELECT 1 FROM document WHERE source_id = ? AND source_ref = ? LIMIT 1",
                (source_id, source_ref),
            )
        )
        return len(rows) > 0

    def document_count(self) -> int:
        return int(next(self._conn.execute("SELECT COUNT(*) FROM document"))[0])

    def latest_published(self, source_id: str) -> date | None:
        row = next(
            self._conn.execute(
                "SELECT MAX(published_at) FROM document WHERE source_id = ?", (source_id,)
            )
        )
        return date.fromisoformat(row[0]) if row[0] else None

    def source_breakdown(self) -> list[SourceStat]:
        """Per-source document counts + last ingest time (for the trust provenance table).

        `document.fetched_at` isn't populated, so last-fetched comes from the latest
        `ingest_run.finished_at` for each source. Ordered by document count, descending.
        """
        rows = self._conn.execute(
            """
            SELECT s.id, s.name, s.licence, s.access_method,
                   COUNT(d.id) AS doc_count,
                   (SELECT MAX(finished_at) FROM ingest_run r WHERE r.source_id = s.id)
            FROM source s
            LEFT JOIN document d ON d.source_id = s.id
            GROUP BY s.id, s.name, s.licence, s.access_method
            ORDER BY doc_count DESC, s.name
            """
        )
        return [
            SourceStat(
                id=sid,
                name=name,
                licence=licence or "",
                access_method=access or "",
                document_count=int(count),
                last_fetched=datetime.fromisoformat(last) if last else None,
            )
            for sid, name, licence, access, count, last in rows
        ]

    def upsert_chunks(
        self,
        document_id: str,
        chunks: list[Chunk],
        vectors: list[list[float]] | None = None,
        model_id: str | None = None,
    ) -> None:
        if vectors is not None and len(vectors) != len(chunks):
            raise ValueError("vectors length must match chunks length")
        with self._conn:
            old_ids = [
                r[0]
                for r in self._conn.execute(
                    "SELECT id FROM chunk WHERE document_id = ?", (document_id,)
                )
            ]
            for cid in old_ids:
                self._conn.execute("DELETE FROM chunk_vec WHERE chunk_id = ?", (cid,))
                self._conn.execute("DELETE FROM chunk_fts WHERE chunk_id = ?", (cid,))
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
            self._conn.executemany(
                "INSERT INTO chunk_fts (chunk_id, text) VALUES (?, ?)",
                [(f"{document_id}#{c.ordinal}", c.text) for c in chunks],
            )
            if vectors is not None:
                self._conn.executemany(
                    "INSERT INTO chunk_vec (chunk_id, embedding) VALUES (?, ?)",
                    [
                        (f"{document_id}#{c.ordinal}", sqlite_vec.serialize_float32(v))
                        for c, v in zip(chunks, vectors, strict=True)
                    ],
                )

    def chunk_count(self, document_id: str | None = None) -> int:
        if document_id is None:
            return int(next(self._conn.execute("SELECT COUNT(*) FROM chunk"))[0])
        return int(
            next(
                self._conn.execute(
                    "SELECT COUNT(*) FROM chunk WHERE document_id = ?", (document_id,)
                )
            )[0]
        )

    def record_ingest_run(self, run: IngestRun) -> int:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO ingest_run
                    (source_id, started_at, finished_at, status, docs_seen,
                     docs_new, docs_updated, error)
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
        return int(self._conn.last_insert_rowid())

    def ingest_run_count(self) -> int:
        return int(next(self._conn.execute("SELECT COUNT(*) FROM ingest_run"))[0])

    @staticmethod
    def _filter_clause(filters: Filters | None) -> tuple[str, list[str]]:
        """An AND-prefixed WHERE fragment + params for `document` filters."""
        if filters is None:
            return "", []
        clauses: list[str] = []
        params: list[str] = []
        if filters.date_from is not None:
            clauses.append("d.published_at >= ?")
            params.append(filters.date_from.isoformat())
        if filters.date_to is not None:
            clauses.append("d.published_at <= ?")
            params.append(filters.date_to.isoformat())
        if filters.sources:
            placeholders = ", ".join("?" for _ in filters.sources)
            clauses.append(f"d.source_id IN ({placeholders})")
            params.extend(filters.sources)
        if filters.region is not None:
            from odr.geo import classify

            resolved = classify(filters.region)
            clauses.append("d.region_code = ?")
            params.append(resolved.code if resolved is not None else filters.region)
        return (" AND " + " AND ".join(clauses), params) if clauses else ("", [])

    def region_breakdown(self) -> list[RegionStat]:
        """Per-ITL-1-region corpus counts for the trust choropleth.

        Every region appears (count 0 if absent); documents with no resolvable
        delivery region are appended as a single ``code=None`` "unspecified" row.
        """
        from odr.geo import REGIONS

        rows = self._conn.execute("SELECT region_code, COUNT(*) FROM document GROUP BY region_code")
        counts = {code: int(n) for code, n in rows}
        stats = [
            RegionStat(code=r.code, name=r.name, document_count=counts.get(r.code, 0))
            for r in REGIONS
        ]
        if counts.get(None):
            stats.append(
                RegionStat(code=None, name="Region not specified", document_count=counts[None])
            )
        return stats

    def semantic_search(
        self, query_vec: list[float], k: int, filters: Filters | None = None
    ) -> list[ScoredChunk]:
        # Filters apply after the KNN candidate set (over-fetch + post-filter); a
        # restrictive filter over a large corpus may want a larger pool (#21 note).
        clause, fparams = self._filter_clause(filters)
        rows = self._conn.execute(
            f"""
            WITH knn AS (
                SELECT chunk_id, distance
                FROM chunk_vec
                WHERE embedding MATCH ?
                ORDER BY distance
                LIMIT ?
            )
            SELECT knn.chunk_id, knn.distance, c.document_id, COALESCE(d.title, ''), c.text,
                   COALESCE(s.name, d.source_id), COALESCE(d.url, ''), d.published_at
            FROM knn
            JOIN chunk c ON c.id = knn.chunk_id
            JOIN document d ON d.id = c.document_id
            LEFT JOIN source s ON s.id = d.source_id
            WHERE 1 = 1{clause}
            ORDER BY knn.distance
            """,
            (sqlite_vec.serialize_float32(query_vec), k, *fparams),
        )
        results: list[ScoredChunk] = []
        for chunk_id, distance, document_id, title, text, source_name, url, published in rows:
            results.append(
                ScoredChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    title=title,
                    text=text,
                    score=1.0 / (1.0 + distance),
                    source_name=source_name,
                    url=url,
                    published_at=date.fromisoformat(published) if published else None,
                )
            )
        return results

    def keyword_search(
        self, query: str, k: int, filters: Filters | None = None
    ) -> list[ScoredChunk]:
        # TODO(odr): apply date/source `filters` in #21.
        tokens = re.findall(r"\w+", query.lower())
        if not tokens:
            return []
        match = " OR ".join(tokens)  # recall-oriented; ranks feed RRF fusion in #20
        clause, fparams = self._filter_clause(filters)
        rows = self._conn.execute(
            f"""
            WITH kw AS (
                SELECT chunk_id, bm25(chunk_fts) AS rank
                FROM chunk_fts
                WHERE chunk_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            )
            SELECT kw.chunk_id, kw.rank, c.document_id, COALESCE(d.title, ''), c.text,
                   COALESCE(s.name, d.source_id), COALESCE(d.url, ''), d.published_at
            FROM kw
            JOIN chunk c ON c.id = kw.chunk_id
            JOIN document d ON d.id = c.document_id
            LEFT JOIN source s ON s.id = d.source_id
            WHERE 1 = 1{clause}
            ORDER BY kw.rank
            """,
            (match, k, *fparams),
        )
        results: list[ScoredChunk] = []
        for chunk_id, rank, document_id, title, text, source_name, url, published in rows:
            results.append(
                ScoredChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    title=title,
                    text=text,
                    score=-float(rank),  # bm25: more-negative is better -> flip to higher-is-better
                    source_name=source_name,
                    url=url,
                    published_at=date.fromisoformat(published) if published else None,
                )
            )
        return results
