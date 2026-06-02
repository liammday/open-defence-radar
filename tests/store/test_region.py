from datetime import date

import apsw

from odr.store.sqlite_store import SqliteStore
from odr.types import Document, Filters


def _doc(ref, region_code):
    return Document(
        source_id="contracts-finder",
        source_ref=ref,
        title=f"n{ref}",
        url="http://x",
        text="body",
        content_hash=ref,
        published_at=date(2026, 1, 1),
        region_code=region_code,
    )


def test_region_persisted_and_breakdown(tmp_path):
    store = SqliteStore(tmp_path / "t.sqlite3")
    store.init_schema()
    store.upsert_document(_doc("a", "UKI"))
    store.upsert_document(_doc("b", "UKI"))
    store.upsert_document(_doc("c", "UKJ"))
    store.upsert_document(_doc("d", None))
    breakdown = {rs.code: rs.document_count for rs in store.region_breakdown()}
    assert breakdown["UKI"] == 2 and breakdown["UKJ"] == 1
    assert breakdown[None] == 1  # unspecified bucket


def test_migration_adds_region_column_to_legacy_db(tmp_path):
    # Simulate a pre-Phase-5 DB: build the document table without region_code.
    p = tmp_path / "legacy.sqlite3"
    con = apsw.Connection(str(p))
    con.execute(
        "CREATE TABLE document (id TEXT PRIMARY KEY, source_id TEXT NOT NULL, "
        "source_ref TEXT NOT NULL, title TEXT, url TEXT, published_at TEXT, "
        "fetched_at TEXT, content_hash TEXT NOT NULL, text TEXT NOT NULL, raw TEXT, "
        "UNIQUE (source_id, source_ref))"
    )
    con.close()
    store = SqliteStore(p)
    store.init_schema()  # must add the column, not crash
    store.upsert_document(_doc("a", "UKM"))
    assert {rs.code: rs.document_count for rs in store.region_breakdown()}["UKM"] == 1


def test_region_filter_clause():
    clause, params = SqliteStore._filter_clause(Filters(region="UKJ"))
    assert "d.region_code = ?" in clause and params == ["UKJ"]
    # a region name is normalised to its ITL-1 code
    assert SqliteStore._filter_clause(Filters(region="South East"))[1] == ["UKJ"]
