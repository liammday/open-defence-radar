"""Behaviour tests for the Store contract.

Each behaviour runs against BOTH the SQLite and in-memory implementations via
the parametrised ``store`` fixture, proving they are interchangeable behind the
``Store`` protocol.
"""

from __future__ import annotations

from datetime import date, datetime

import apsw
import pytest

from odr.store.base import Store
from odr.store.memory_store import InMemoryStore
from odr.store.sqlite_store import SqliteStore
from odr.types import Chunk, Document, Filters, IngestRun, SourceMeta


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


def test_upsert_and_get_source_records_provenance(store) -> None:  # type: ignore[no-untyped-def]
    meta = SourceMeta(
        id="contracts-finder",
        name="UK Contracts Finder",
        url="https://www.contractsfinder.service.gov.uk",
        access_method="OCDS API",
        licence="OGL v3.0",
        attribution=(
            "Contains public sector information licensed under the Open Government Licence v3.0."
        ),
    )
    store.upsert_source(meta)
    got = store.get_source("contracts-finder")
    assert got is not None
    assert got.licence == "OGL v3.0"
    assert got.access_method == "OCDS API"
    assert store.get_source("missing") is None


def _seed_two_chunks(store) -> tuple[str, str]:  # type: ignore[no-untyped-def]
    a = store.upsert_document(
        _doc(ref="r1", text="artificial intelligence platform", content_hash="h1")
    )
    store.upsert_chunks(a, [Chunk(a, 0, "artificial intelligence platform", 3)])
    b = store.upsert_document(
        _doc(ref="r2", text="passenger transport services", content_hash="h2")
    )
    store.upsert_chunks(b, [Chunk(b, 0, "passenger transport services", 3)])
    return f"{a}#0", f"{b}#0"


def test_keyword_search_matches_only_relevant_chunks(store) -> None:  # type: ignore[no-untyped-def]
    ai_chunk, _ = _seed_two_chunks(store)
    hits = store.keyword_search("intelligence", k=5)
    assert [h.chunk_id for h in hits] == [ai_chunk]
    assert hits[0].text == "artificial intelligence platform"


def test_keyword_search_no_match_returns_empty(store) -> None:  # type: ignore[no-untyped-def]
    _seed_two_chunks(store)
    assert store.keyword_search("zzzznotpresent", k=5) == []
    assert store.keyword_search("   ", k=5) == []


def _seed_two_sources_text(store) -> tuple[str, str]:  # type: ignore[no-untyped-def]
    """Same text 'alpha signal' from two sources / dates, one chunk each (no vectors)."""
    a = store.upsert_document(
        Document("contracts-finder", "r1", "t", "u", "alpha signal", "h1", date(2026, 1, 1))
    )
    store.upsert_chunks(a, [Chunk(a, 0, "alpha signal", 2)])
    b = store.upsert_document(
        Document("find-a-tender", "r2", "t", "u", "alpha signal", "h2", date(2025, 1, 1))
    )
    store.upsert_chunks(b, [Chunk(b, 0, "alpha signal", 2)])
    return a, b


def test_keyword_search_filters_by_source_and_date(store) -> None:  # type: ignore[no-untyped-def]
    a, _ = _seed_two_sources_text(store)
    assert len(store.keyword_search("alpha", k=10)) == 2  # unfiltered: both
    by_source = store.keyword_search("alpha", k=10, filters=Filters(sources=("contracts-finder",)))
    assert [h.document_id for h in by_source] == [a]
    by_date = store.keyword_search("alpha", k=10, filters=Filters(date_from=date(2026, 1, 1)))
    assert [h.document_id for h in by_date] == [a]


def test_semantic_search_filters_by_source(vec_store) -> None:  # type: ignore[no-untyped-def]
    a = vec_store.upsert_document(
        Document("contracts-finder", "r1", "t", "u", "alpha signal", "h1", date(2026, 1, 1))
    )
    vec_store.upsert_chunks(a, [Chunk(a, 0, "alpha", 1)], vectors=[[1.0, 0.0, 0.0]], model_id="m")
    b = vec_store.upsert_document(
        Document("find-a-tender", "r2", "t", "u", "alpha signal", "h2", date(2025, 1, 1))
    )
    vec_store.upsert_chunks(b, [Chunk(b, 0, "alpha", 1)], vectors=[[1.0, 0.0, 0.0]], model_id="m")
    hits = vec_store.semantic_search(
        [1.0, 0.0, 0.0], k=10, filters=Filters(sources=("contracts-finder",))
    )
    assert [h.document_id for h in hits] == [a]


def test_sqlite_creates_tables_and_enables_wal(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "odr.sqlite3"
    SqliteStore(path).init_schema()
    con = apsw.Connection(str(path))
    try:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"source", "document", "chunk", "ingest_run"} <= tables
        assert list(con.execute("PRAGMA journal_mode"))[0][0].lower() == "wal"
    finally:
        con.close()


@pytest.fixture(params=["memory", "sqlite"])
def vec_store(request: pytest.FixtureRequest, tmp_path):  # type: ignore[no-untyped-def]
    """A store configured for 3-dimensional vectors, populated via upsert_chunks."""
    if request.param == "memory":
        s: InMemoryStore | SqliteStore = InMemoryStore()
    else:
        s = SqliteStore(tmp_path / "vec.sqlite3", dim=3)
    s.init_schema()
    return s


def test_semantic_search_returns_nearest_first(vec_store) -> None:  # type: ignore[no-untyped-def]
    doc_id = vec_store.upsert_document(_doc())
    vec_store.upsert_chunks(
        doc_id,
        [Chunk(doc_id, 0, "about cats", 2), Chunk(doc_id, 1, "about dogs", 2)],
        vectors=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        model_id="test-model",
    )
    hits = vec_store.semantic_search([0.9, 0.1, 0.0], k=2)
    assert len(hits) == 2
    assert hits[0].chunk_id == f"{doc_id}#0"  # nearest to the query vector
    assert hits[0].score >= hits[1].score
    assert hits[0].document_id == doc_id
    assert hits[0].text == "about cats"
