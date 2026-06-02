import json

from odr.query import build_filters
from odr.sources.ocds import delivery_region_code
from odr.store.sqlite_store import SqliteStore
from odr.types import Document


def test_build_filters_includes_region():
    f = build_filters(region="South East")
    assert f is not None and f.region == "South East"


def test_build_filters_none_when_all_empty():
    assert build_filters() is None


def test_backfill_region_codes_from_raw(tmp_path):
    store = SqliteStore(tmp_path / "b.sqlite3")
    store.init_schema()
    raw = {
        "ocid": "x",
        "tender": {"title": "t", "items": [{"deliveryAddresses": [{"region": "Scotland"}]}]},
    }
    # A document stored before Phase 5: region in raw, but region_code not yet derived.
    store.upsert_document(
        Document(
            source_id="contracts-finder",
            source_ref="r1",
            title="t",
            url="u",
            text="b",
            content_hash="h1",
            raw=raw,
            region_code=None,
        )
    )
    changed = store.backfill_region_codes(
        lambda rj: delivery_region_code(json.loads(rj)) if rj else None
    )
    assert changed == 1
    breakdown = {rs.code: rs.document_count for rs in store.region_breakdown()}
    assert breakdown.get("UKM") == 1  # Scotland
