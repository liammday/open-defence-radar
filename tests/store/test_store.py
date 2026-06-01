"""Behaviour tests for the Store contract.

Each behaviour runs against BOTH the SQLite and in-memory implementations via
the parametrised ``store`` fixture, proving they are interchangeable behind the
``Store`` protocol.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime

import pytest

from odr.store.base import Store
from odr.store.memory_store import InMemoryStore
from odr.store.sqlite_store import SqliteStore
from odr.types import Chunk, Document, IngestRun


def _requires_store(_s: Store) -> None:
    """No-op whose signature makes mypy enforce Store conformance below."""


def test_both_stores_conform_to_protocol() -> None:
    # Fails type-checking (mypy) if either store drifts from the Store contract.
    _requires_store(InMemoryStore())
    _requires_store(SqliteStore(":memory:"))


@pytest.fixture(params=["memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path):  # type: ignore[no-untyped-def]
    if request.param == "memory":
        s: InMemoryStore | SqliteStore = InMemoryStore()
    else:
        s = SqliteStore(tmp_path / "odr.sqlite3")
    s.init_schema()
    return s


def _doc(ref: str = "ocid-1", text: str = "hello world", content_hash: str = "h1") -> Document:
    return Document(
        source_id="contracts-finder",
        source_ref=ref,
        title="A contract notice",
        url="https://example.gov.uk/notice/1",
        text=text,
        content_hash=content_hash,
        published_at=date(2026, 1, 1),
    )


def test_unknown_content_hash_is_absent(store) -> None:  # type: ignore[no-untyped-def]
    assert store.content_hash_exists("does-not-exist") is False


def test_upsert_document_then_hash_exists(store) -> None:  # type: ignore[no-untyped-def]
    store.upsert_document(_doc())
    assert store.content_hash_exists("h1") is True
    assert store.document_count() == 1


def test_reupsert_same_ref_updates_not_duplicates(store) -> None:  # type: ignore[no-untyped-def]
    store.upsert_document(_doc(text="old", content_hash="h1"))
    store.upsert_document(_doc(text="new", content_hash="h2"))  # same source_id+ref
    assert store.document_count() == 1
    assert store.content_hash_exists("h2") is True
    assert store.content_hash_exists("h1") is False


def test_upsert_chunks_counts_per_document(store) -> None:  # type: ignore[no-untyped-def]
    doc_id = store.upsert_document(_doc())
    store.upsert_chunks(
        doc_id,
        [Chunk(doc_id, 0, "first", 1), Chunk(doc_id, 1, "second", 1)],
    )
    assert store.chunk_count(doc_id) == 2


def test_record_ingest_run(store) -> None:  # type: ignore[no-untyped-def]
    store.record_ingest_run(
        IngestRun(
            source_id="contracts-finder",
            started_at=datetime(2026, 1, 1, 4, 0, 0),
            finished_at=datetime(2026, 1, 1, 4, 1, 0),
            status="ok",
            docs_seen=10,
            docs_new=10,
            docs_updated=0,
        )
    )
    assert store.ingest_run_count() == 1


def test_sqlite_creates_tables_and_enables_wal(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "odr.sqlite3"
    SqliteStore(path).init_schema()
    con = sqlite3.connect(path)
    try:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"source", "document", "chunk", "ingest_run"} <= tables
        assert con.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        con.close()
