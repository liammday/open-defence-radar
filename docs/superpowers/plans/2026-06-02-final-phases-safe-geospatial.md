# Final phases — safe geospatial (v0.6.0) → v1.0.0 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a guardrail-safe, region-level geospatial capability (extract → filter → map the UK ITL-1 delivery region already present in the OGL procurement data), then complete the v1.0.0 Definition of Done.

**Architecture:** A pure ITL-1 gazetteer (`odr/geo`) normalises OCDS region strings/NUTS codes to one of 12 UK regions. The OCDS normaliser extracts a `region_code` onto each `Document`; the store persists it (additive migration), filters on it, and aggregates a per-region corpus breakdown. The region threads through `Filters` to the CLI, MCP tool, and web `/query`. The trust dashboard renders a self-hosted **tile-grid choropleth** (12 equal labelled cells, shaded by count, with an a11y text-table fallback). Region-level only — nothing can resolve finer than a region.

**Tech Stack:** Python 3.12, apsw/SQLite + FTS5 + sqlite-vec, Typer CLI, FastMCP, FastAPI + Jinja2, pytest/ruff/mypy. No new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-06-02-final-phases-safe-geospatial-design.md`

---

## File structure

| File | Responsibility |
|---|---|
| `src/odr/geo/__init__.py` (create) | Package marker, re-export `Region`, `REGIONS`, `classify`. |
| `src/odr/geo/regions.py` (create) | The 12-region ITL-1 gazetteer + `classify()`. Pure, no I/O. |
| `src/odr/types.py` (modify) | Add `Document.region_code`, `Filters.region`, new `RegionStat`. |
| `src/odr/sources/ocds.py` (modify) | Extract delivery region in `normalise`. |
| `src/odr/store/sqlite_store.py` (modify) | `region_code` column + migration, persist, filter, `region_breakdown`. |
| `src/odr/store/memory_store.py` (modify) | Mirror region filter + `region_breakdown` (test double). |
| `src/odr/store/base.py` (modify) | Add `region_breakdown` to the `Store` protocol. |
| `src/odr/query.py` (modify) | `build_filters` gains a `region` param. |
| `src/odr/cli.py` (modify) | `query --region`; new `geo backfill` command. |
| `src/odr/mcp_server/server.py` (modify) | `query` tool gains a `region` arg. |
| `src/odr/web/app.py` (modify) | `QueryRequest.region`; `SiteContext.geo`; populate it. |
| `src/odr/web/geo_view.py` (create) | `GeoView`/`RegionCell` view-model for the choropleth. |
| `src/odr/web/templates/trust.html` (modify) | Render the tile-grid choropleth + a11y table. |
| `src/odr/web/static/app.css` (modify) | Choropleth tile styling + colourblind-safe ramp. |
| `tests/geo/test_regions.py` (create) | `classify` cases. |
| `tests/store/test_region.py` (create) | migration, persist, filter, breakdown. |
| `tests/sources/test_ocds_region.py` (create) | extraction from a fixture. |
| `tests/web/test_geo.py` (create) | choropleth render + a11y + region query param. |
| `README.md` (modify) | Sources & licensing (gazetteer provenance), Status, feature docs. |

---

## Task 1: ITL-1 gazetteer

**Files:** Create `src/odr/geo/__init__.py`, `src/odr/geo/regions.py`, `tests/geo/__init__.py`, `tests/geo/test_regions.py`

- [ ] **Step 1: Write the failing test** — `tests/geo/test_regions.py`

```python
from odr.geo import REGIONS, Region, classify


def test_twelve_itl1_regions_with_centroids():
    assert len(REGIONS) == 12
    codes = {r.code for r in REGIONS}
    assert codes == {"UKC","UKD","UKE","UKF","UKG","UKH","UKI","UKJ","UKK","UKL","UKM","UKN"}
    for r in REGIONS:
        lat, lon = r.centroid
        assert 49.0 < lat < 61.0 and -8.5 < lon < 2.0  # within UK bounds


def test_classify_accepts_name_case_insensitive():
    r = classify("south east")
    assert isinstance(r, Region) and r.code == "UKJ" and r.name == "South East"


def test_classify_accepts_itl1_code():
    assert classify("UKI").name == "London"


def test_classify_truncates_longer_nuts_codes():
    assert classify("UKL24").code == "UKL"      # → Wales
    assert classify("UKH15").code == "UKH"       # → East of England


def test_classify_returns_none_for_country_or_unknown():
    assert classify("UK") is None
    assert classify("England") is None
    assert classify("") is None
    assert classify("Atlantis") is None
```

- [ ] **Step 2: Run test to verify it fails** — `uv run pytest tests/geo/test_regions.py -q` → FAIL (module `odr.geo` not found).

- [ ] **Step 3: Implement** — `src/odr/geo/regions.py`

```python
"""UK ITL-1 (NUTS-1) region gazetteer — names, codes, centroids, and a
normaliser from OCDS region strings/NUTS codes to one of the 12 regions.

Pure, no I/O. ITL-1 code↔name and region centroids are ONS open data
(Open Government Licence v3.0) — see README "Sources & licensing".
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    code: str            # ITL-1 / NUTS-1 code, e.g. "UKJ"
    name: str            # canonical display name, e.g. "South East"
    centroid: tuple[float, float]  # (lat, lon), approx region centre


REGIONS: tuple[Region, ...] = (
    Region("UKC", "North East", (54.93, -1.75)),
    Region("UKD", "North West", (54.00, -2.70)),
    Region("UKE", "Yorkshire and the Humber", (53.80, -1.30)),
    Region("UKF", "East Midlands", (52.90, -0.80)),
    Region("UKG", "West Midlands", (52.50, -2.10)),
    Region("UKH", "East of England", (52.20, 0.45)),
    Region("UKI", "London", (51.51, -0.12)),
    Region("UKJ", "South East", (51.30, -0.70)),
    Region("UKK", "South West", (50.90, -3.50)),
    Region("UKL", "Wales", (52.13, -3.78)),
    Region("UKM", "Scotland", (56.82, -4.18)),
    Region("UKN", "Northern Ireland", (54.61, -6.66)),
)

_BY_CODE = {r.code: r for r in REGIONS}
_BY_NAME = {r.name.lower(): r for r in REGIONS}
# Common alias spellings seen in OCDS deliveryAddresses.region values.
_ALIASES = {
    "yorkshire and humber": "UKE",
    "yorkshire": "UKE",
    "east": "UKH",
}


def classify(value: str | None) -> Region | None:
    """Map a region name or NUTS/ITL code to a Region, or None if not resolvable.

    Accepts "London", "South East", "UKI", or a longer NUTS code truncated to
    its ITL-1 prefix ("UKL24" → "UKL"). Country-level ("UK", "England") and
    unknown values return None.
    """
    if not value:
        return None
    v = value.strip()
    if not v:
        return None
    upper = v.upper()
    if upper.startswith("UK") and len(upper) >= 3:
        prefix = upper[:3]
        if prefix in _BY_CODE:
            return _BY_CODE[prefix]
    lower = v.lower()
    if lower in _BY_NAME:
        return _BY_NAME[lower]
    if lower in _ALIASES:
        return _BY_CODE[_ALIASES[lower]]
    return None
```

And `src/odr/geo/__init__.py`:

```python
"""Geospatial support — UK ITL-1 region gazetteer (region-level, analytic only)."""
from odr.geo.regions import REGIONS, Region, classify

__all__ = ["REGIONS", "Region", "classify"]
```

Create empty `tests/geo/__init__.py`.

- [ ] **Step 4: Run tests** — `uv run pytest tests/geo/test_regions.py -q` → PASS.
- [ ] **Step 5: Lint + commit** — `uv run ruff check src/odr/geo tests/geo && uv run mypy src/odr/geo`

```bash
git add src/odr/geo tests/geo
git commit -m "feat(geo): UK ITL-1 region gazetteer + classify (#7)"
```

---

## Task 2: extract delivery region in the OCDS normaliser

**Files:** Modify `src/odr/types.py`, `src/odr/sources/ocds.py`; create `tests/sources/test_ocds_region.py`

- [ ] **Step 1: Write the failing test** — `tests/sources/test_ocds_region.py`

```python
from odr.sources.contracts_finder import ContractsFinder


def _release(region):
    return {
        "ocid": "ocds-b5fd17-x",
        "date": "2026-01-02T00:00:00Z",
        "tender": {
            "title": "Test notice",
            "items": [{"id": "1", "deliveryAddresses": [{"region": region}]}],
        },
    }


def test_normalise_extracts_itl1_region_code():
    doc = ContractsFinder().normalise(_release("South East"))
    assert doc.region_code == "UKJ"


def test_normalise_handles_nuts_code_region():
    doc = ContractsFinder().normalise(_release("UKL24"))
    assert doc.region_code == "UKL"


def test_normalise_region_none_when_absent_or_country_level():
    assert ContractsFinder().normalise(_release("England")).region_code is None
    assert ContractsFinder().normalise({"ocid": "x", "tender": {"title": "t"}}).region_code is None
```

- [ ] **Step 2: Run test** — `uv run pytest tests/sources/test_ocds_region.py -q` → FAIL (`Document` has no `region_code` / not extracted).

- [ ] **Step 3a: Implement — `Document.region_code`** in `src/odr/types.py` (add as the last field of `Document`, after `raw`):

```python
    raw: dict | None = None  # the original payload, kept for provenance/debug
    region_code: str | None = None  # UK ITL-1 code (delivery region), or None
```

- [ ] **Step 3b: Implement — extraction** in `src/odr/sources/ocds.py`. Add an import `from odr.geo import classify` and a helper, then set `region_code` in the returned `Document`:

```python
def _delivery_region_code(raw: Mapping[str, Any]) -> str | None:
    for item in (raw.get("tender") or {}).get("items") or []:
        for addr in item.get("deliveryAddresses") or []:
            region = classify(addr.get("region"))
            if region is not None:
                return region.code
    return None
```

In `normalise`, add `region_code=_delivery_region_code(raw),` to the `Document(...)` constructor call.

- [ ] **Step 4: Run tests** — `uv run pytest tests/sources/test_ocds_region.py tests/sources -q` → PASS (existing source tests still pass).
- [ ] **Step 5: Lint + commit**

```bash
git add src/odr/types.py src/odr/sources/ocds.py tests/sources/test_ocds_region.py
git commit -m "feat(ingest): extract ITL-1 delivery region onto Document (#7)"
```

---

## Task 3: store — region column, persistence, migration, filter, breakdown

**Files:** Modify `src/odr/types.py`, `src/odr/store/sqlite_store.py`, `src/odr/store/memory_store.py`, `src/odr/store/base.py`; create `tests/store/test_region.py`

- [ ] **Step 1: Write the failing test** — `tests/store/test_region.py`

```python
from datetime import date

from odr.store.sqlite_store import SqliteStore
from odr.types import Document, Filters


def _doc(ref, region_code):
    return Document(
        source_id="contracts-finder", source_ref=ref, title=f"n{ref}",
        url="http://x", text="body", content_hash=ref, published_at=date(2026, 1, 1),
        region_code=region_code,
    )


def test_region_persisted_and_breakdown(tmp_path):
    store = SqliteStore(tmp_path / "t.sqlite3"); store.init_schema()
    store.upsert_document(_doc("a", "UKI"))
    store.upsert_document(_doc("b", "UKI"))
    store.upsert_document(_doc("c", "UKJ"))
    store.upsert_document(_doc("d", None))
    breakdown = {rs.code: rs.document_count for rs in store.region_breakdown()}
    assert breakdown["UKI"] == 2 and breakdown["UKJ"] == 1
    assert breakdown[None] == 1  # unspecified bucket


def test_migration_adds_region_column_to_legacy_db(tmp_path):
    # Simulate a pre-Phase-5 DB: build schema without region_code, then reopen.
    p = tmp_path / "legacy.sqlite3"
    import apsw
    con = apsw.Connection(str(p))
    con.execute(
        "CREATE TABLE document (id TEXT PRIMARY KEY, source_id TEXT NOT NULL, "
        "source_ref TEXT NOT NULL, title TEXT, url TEXT, published_at TEXT, "
        "fetched_at TEXT, content_hash TEXT NOT NULL, text TEXT NOT NULL, raw TEXT, "
        "UNIQUE (source_id, source_ref))"
    )
    con.close()
    store = SqliteStore(p); store.init_schema()  # must add the column, not crash
    store.upsert_document(_doc("a", "UKM"))
    assert {rs.code: rs.document_count for rs in store.region_breakdown()}["UKM"] == 1
```

Add a filter test (in the same file):

```python
def test_region_filter_clause():
    clause, params = SqliteStore._filter_clause(Filters(region="UKJ"))
    assert "d.region_code = ?" in clause and params == ["UKJ"]
    assert SqliteStore._filter_clause(Filters(region="South East"))[1] == ["UKJ"]  # normalised
```

- [ ] **Step 2: Run test** — `uv run pytest tests/store/test_region.py -q` → FAIL.

- [ ] **Step 3a: `Filters.region`** in `src/odr/types.py` (`Filters` dataclass):

```python
    sources: tuple[str, ...] | None = None
    region: str | None = None  # UK ITL-1 code or name (Phase 5); normalised on use
```

- [ ] **Step 3b: `RegionStat`** in `src/odr/types.py` (new frozen dataclass near `SourceStat`):

```python
@dataclass(frozen=True)
class RegionStat:
    """Per-region corpus count for the trust choropleth. code=None → unspecified."""
    code: str | None
    name: str
    document_count: int
```

- [ ] **Step 3c: schema + migration + persist + filter + breakdown** in `src/odr/store/sqlite_store.py`:
  - In `_RELATIONAL_SCHEMA`, add `region_code TEXT,` to the `document` CREATE TABLE (after `raw TEXT,`) and `CREATE INDEX IF NOT EXISTS idx_document_region ON document (region_code);`.
  - In `init_schema`, after executing the schema, call a guarded migration:

```python
    def init_schema(self) -> None:
        self._conn.execute(_RELATIONAL_SCHEMA)
        self._ensure_column("document", "region_code", "TEXT")
        # ... existing virtual-table creation ...

    def _ensure_column(self, table: str, column: str, decl: str) -> None:
        cols = {r[1] for r in self._conn.execute(f"PRAGMA table_info({table})")}
        if column not in cols:
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
```

  - In `upsert_document`, add `region_code` to the column list, the values tuple (`doc.region_code`), and the `ON CONFLICT ... DO UPDATE SET` list (`region_code=excluded.region_code`).
  - In `_filter_clause`, before the return, add:

```python
        if filters.region is not None:
            from odr.geo import classify
            r = classify(filters.region)
            clauses.append("d.region_code = ?")
            params.append(r.code if r is not None else filters.region)
```

  - Add `region_breakdown`:

```python
    def region_breakdown(self) -> list[RegionStat]:
        from odr.geo import REGIONS
        names = {r.code: r.name for r in REGIONS}
        rows = self._conn.execute(
            "SELECT region_code, COUNT(*) FROM document GROUP BY region_code"
        )
        counts = {code: int(n) for code, n in rows}
        stats = [
            RegionStat(code=r.code, name=r.name, document_count=counts.get(r.code, 0))
            for r in REGIONS
        ]
        if counts.get(None):
            stats.append(RegionStat(code=None, name="Region not specified", document_count=counts[None]))
        return stats
```

  Import `RegionStat` at the top of the module.

- [ ] **Step 3d: mirror in `memory_store.py` and `base.py`.**
  - `_passes`: before the final return, add `if filters.region is not None: from odr.geo import classify; r = classify(filters.region); code = r.code if r else filters.region; if doc.region_code != code: return False`.
  - Add `region_breakdown(self) -> list[RegionStat]` to `InMemoryStore` (aggregate `self._documents` by `region_code`, same shape as SQLite).
  - Add `def region_breakdown(self) -> list[RegionStat]: ...` to the `Store` protocol in `base.py` and import `RegionStat`.

- [ ] **Step 4: Run tests** — `uv run pytest tests/store -q` → PASS.
- [ ] **Step 5: Lint + commit**

```bash
git add src/odr/types.py src/odr/store tests/store/test_region.py
git commit -m "feat(store): persist + filter + aggregate ITL-1 region (additive migration) (#7)"
```

---

## Task 4: region threads through query + backfill command

**Files:** Modify `src/odr/query.py`, `src/odr/cli.py`; create `tests/test_geo_cli.py`

- [ ] **Step 1: Write the failing test** — `tests/test_geo_cli.py`

```python
from odr.query import build_filters


def test_build_filters_includes_region():
    f = build_filters(region="South East")
    assert f is not None and f.region == "South East"


def test_build_filters_none_when_all_empty():
    assert build_filters() is None
```

- [ ] **Step 2: Run** — `uv run pytest tests/test_geo_cli.py -q` → FAIL (`build_filters` has no `region`).

- [ ] **Step 3a: `build_filters` region param** in `src/odr/query.py`:

```python
def build_filters(date_from=None, date_to=None, sources=None, region=None):
    if not (date_from or date_to or sources or region):
        return None
    return Filters(
        date_from=date.fromisoformat(date_from) if date_from else None,
        date_to=date.fromisoformat(date_to) if date_to else None,
        sources=tuple(sources) if sources else None,
        region=region or None,
    )
```

(keep the existing type hints; add `region: str | None = None`.)

- [ ] **Step 3b: CLI `query --region`** in `src/odr/cli.py` `query` command: add option
  `region: str | None = typer.Option(None, "--region", help="Restrict to a UK ITL-1 region (name or code)")`
  and pass `region=region` into `build_filters(...)`.

- [ ] **Step 3c: `geo backfill` command** in `src/odr/cli.py`:

```python
geo_app = typer.Typer(help="Geospatial maintenance (region-level, analytic only).")
app.add_typer(geo_app, name="geo")


@geo_app.command("backfill")
def geo_backfill() -> None:
    """Re-derive region_code for stored OCDS docs from their retained raw payload."""
    import json
    from odr.geo import classify
    store = SqliteStore(os.environ.get("ODR_DB_PATH", "data/odr.sqlite3"))
    store.init_schema()
    updated = store.backfill_region_codes(
        lambda raw: _delivery_region_from_raw(json.loads(raw)) if raw else None
    )
    typer.echo(f"backfilled region_code on {updated} documents")
```

  Add helper `_delivery_region_from_raw` mirroring Task 2's extraction (import or re-use `odr.sources.ocds._delivery_region_code`; expose it). Add `backfill_region_codes(self, derive)` to `SqliteStore`: iterate `SELECT id, raw FROM document`, compute `derive(raw)`, `UPDATE document SET region_code=? WHERE id=?`, return the count changed. (No `base.py` change needed — backfill is SQLite-specific maintenance.)

- [ ] **Step 4: Run** — `uv run pytest tests/test_geo_cli.py -q` and a manual `uv run odr geo backfill` against `data/odr.sqlite3`; expect "backfilled region_code on 31 documents" (matches the 40% coverage from the spec §2).
- [ ] **Step 5: Commit**

```bash
git add src/odr/query.py src/odr/cli.py src/odr/store/sqlite_store.py tests/test_geo_cli.py
git commit -m "feat(cli): query --region + geo backfill command (#7)"
```

---

## Task 5: region param on the MCP tool + web /query

**Files:** Modify `src/odr/mcp_server/server.py`, `src/odr/web/app.py`; create/extend `tests/web/test_geo.py`

- [ ] **Step 1: Write the failing test** — `tests/web/test_geo.py` (query-param half)

```python
from odr.web.app import create_app
from fastapi.testclient import TestClient


def _fake_query(topic, k, filters):
    from odr.types import Answer, GroundednessReport
    _fake_query.seen = filters
    return Answer(text="ok", citations=(), groundedness=GroundednessReport(0, 0, 0), retrieved=())


def test_query_route_forwards_region():
    app = create_app(query_fn=_fake_query)
    client = TestClient(app)
    r = client.post("/query", json={"topic": "x", "region": "South East"})
    assert r.status_code == 200
    assert _fake_query.seen is not None and _fake_query.seen.region == "South East"
```

- [ ] **Step 2: Run** — `uv run pytest tests/web/test_geo.py -q` → FAIL.
- [ ] **Step 3a:** `QueryRequest` in `app.py`: add `region: str | None = None`; in the `/query` route pass `req.region` into `build_filters(req.date_from, req.date_to, req.sources, req.region)`.
- [ ] **Step 3b:** MCP `query` tool in `mcp_server/server.py`: add a `region: str | None = None` argument and pass it to `build_filters(...)` (mirror the existing date/sources wiring).
- [ ] **Step 4: Run** — `uv run pytest tests/web/test_geo.py tests/mcp_server -q` → PASS.
- [ ] **Step 5: Commit**

```bash
git add src/odr/mcp_server/server.py src/odr/web/app.py tests/web/test_geo.py
git commit -m "feat(mcp,web): region filter on the query tool + /query route (#7)"
```

---

## Task 6: tile-grid choropleth on the trust dashboard

**Files:** Create `src/odr/web/geo_view.py`; modify `src/odr/web/app.py`, `templates/trust.html`, `static/app.css`; extend `tests/web/test_geo.py`

- [ ] **Step 1: Write the failing test** — extend `tests/web/test_geo.py`

```python
from odr.web.geo_view import GeoView, build_geo_view
from odr.types import RegionStat


def test_geo_view_buckets_and_unspecified():
    stats = [RegionStat("UKI", "London", 7), RegionStat("UKJ", "South East", 1),
             RegionStat(None, "Region not specified", 46)]
    view = build_geo_view(stats)
    assert view.placed_total == 8 and view.unspecified == 46
    london = next(c for c in view.cells if c.code == "UKI")
    assert london.count == 7 and london.intensity > 0  # 0..1 ramp


def test_trust_page_renders_choropleth_and_a11y_table(monkeypatch):
    from odr.web.app import create_app, SiteContext
    from odr.web.geo_view import build_geo_view
    from fastapi.testclient import TestClient

    def ctx():
        return SiteContext(source_count=3, document_count=54, provenance=(),
                           trust=None,
                           geo=build_geo_view([RegionStat("UKI", "London", 7),
                                               RegionStat(None, "Region not specified", 47)]))
    client = TestClient(create_app(context_provider=ctx))
    html = client.get("/trust").text
    assert "London" in html and "Region not specified" in html
    assert 'class="tilemap"' in html  # the SVG choropleth
    assert "<table" in html           # a11y text-table fallback
```

- [ ] **Step 2: Run** — `uv run pytest tests/web/test_geo.py -q` → FAIL.

- [ ] **Step 3a: `geo_view.py`** — the view-model + fixed tile layout (col,row per region in a roughly-geographic UK grid):

```python
"""Trust-dashboard choropleth view-model: 12 UK regions as a tile grid,
shaded by corpus document count. Region-level, analytic only."""
from __future__ import annotations

from dataclasses import dataclass

from odr.types import RegionStat

# (code, col, row) — a schematic UK layout; Scotland/NI top, London/SE bottom.
_LAYOUT: dict[str, tuple[int, int]] = {
    "UKM": (2, 0), "UKN": (0, 1), "UKC": (2, 1), "UKD": (1, 2), "UKE": (2, 2),
    "UKL": (0, 3), "UKG": (1, 3), "UKF": (2, 3), "UKH": (3, 3),
    "UKK": (1, 4), "UKJ": (2, 4), "UKI": (3, 4),
}


@dataclass(frozen=True)
class RegionCell:
    code: str
    name: str
    count: int
    col: int
    row: int
    intensity: float  # 0..1, count / max placed count


@dataclass(frozen=True)
class GeoView:
    cells: tuple[RegionCell, ...]
    unspecified: int
    placed_total: int

    @property
    def has_data(self) -> bool:
        return self.placed_total > 0 or self.unspecified > 0


def build_geo_view(stats: list[RegionStat]) -> GeoView:
    placed = {s.code: s for s in stats if s.code is not None}
    unspecified = next((s.document_count for s in stats if s.code is None), 0)
    peak = max((s.document_count for s in placed.values()), default=0)
    cells = []
    for code, (col, row) in _LAYOUT.items():
        s = placed.get(code)
        count = s.document_count if s else 0
        name = s.name if s else code
        cells.append(RegionCell(code, name, count, col, row,
                                 intensity=(count / peak) if peak else 0.0))
    placed_total = sum(c.count for c in cells)
    return GeoView(cells=tuple(cells), unspecified=unspecified, placed_total=placed_total)
```

- [ ] **Step 3b: wire into `SiteContext`** in `app.py`: add `geo: GeoView | None` to the dataclass (import from `odr.web.geo_view`); in `_default_context`, `geo=build_geo_view(list(store.region_breakdown()))`.

- [ ] **Step 3c: template** — add a section to `templates/trust.html` (after the provenance table). Render an inline `<svg class="tilemap">` of `site.geo.cells` (one `<rect>` per cell positioned by `col`/`row`, `fill-opacity` from `intensity`, `<title>` = "{name}: {count}"), then a `<table>` listing each region + count and a "Region not specified" row. Guard with `{% if site.geo and site.geo.has_data %}`. Include an `aria-label` on the svg and keep the table as the non-visual fallback.

- [ ] **Step 3d: CSS** — in `static/app.css`, add `.tilemap` sizing + `.tilemap rect` base fill (the existing palette's accent) so `fill-opacity` produces a single-hue sequential ramp (colourblind-safe). Add a `.tilemap rect` stroke for cell separation.

- [ ] **Step 4: Run** — `uv run pytest tests/web -q` → PASS (existing web tests unaffected).
- [ ] **Step 5: Commit**

```bash
git add src/odr/web/geo_view.py src/odr/web/app.py src/odr/web/templates/trust.html src/odr/web/static/app.css tests/web/test_geo.py
git commit -m "feat(web): tile-grid region choropleth on the trust dashboard (#7)"
```

---

## Task 7: docs, provenance, guardrail

**Files:** Modify `README.md`

- [ ] **Step 1:** README "Sources & licensing": add a row recording the **ONS ITL-1 region geography** (names/codes/centroids) as OGL v3.0 with attribution; note the tile-grid map is self-authored (no third-party asset).
- [ ] **Step 2:** README "Status": update to Phase 5 / `v0.6.0`; add a short "Geospatial" subsection describing region-level filtering + the dashboard choropleth, and an explicit note that ACLED / precise geocoding were **declined** for the open-data + analytic-not-operational guardrails.
- [ ] **Step 3:** Run the full suite + lint + types: `uv run pytest -q && uv run ruff check . && uv run mypy src`.
- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(geo): record ITL-1 provenance + Phase 5 status; note declined ACLED (#7)"
```

---

## v0.6.0 release gate

- [ ] Phase 5 milestone issues closed; CI green on the branch; eval thresholds met (`uv run odr eval` then confirm the gate).
- [ ] Guardrail checklist run on the geo PR (labelled `guardrail`).
- [ ] Open PR `feat: Phase 5 — safe geospatial (v0.6.0)`; squash-merge to `main`.
- [ ] Tag `v0.6.0` (after merge), close the Phase 5 milestone.

---

## Part B — v1.0.0 Definition of Done (checklist, not TDD)

- [ ] **B1. Licence** — *user decision MIT vs Apache-2.0.* Add `LICENSE`, set `pyproject` `license = {text=...}` / classifier, update README License section.
- [ ] **B2. Guardrail review** — run the 6-point checklist across the whole repo; record sign-off in the release PR body.
- [ ] **B3. Clean-clone verification** — fresh clone → `uv sync` → `uv run ruff check . && uv run mypy src && uv run pytest -q && uv run odr eval` all green → `uv run odr-web` + `docker compose up` smoke → exercise one cited answer and one `--region` query. Capture evidence.
- [ ] **B4. Docs polish** — README Status → `v1.0.0`; confirm the declined-future-work note (ACLED, precise geocoding) reads clearly.
- [ ] **B5. Flip public** — tag `v1.0.0`, close the DoD milestone, then make the repo public. **Only on explicit user go-ahead** (gated; do not perform autonomously).

---

## Self-review (against the spec)

- **Spec coverage:** A1→Task1; A2→Task2; A3→Task3; A4→Tasks3–5; A5→Task6; A6→Task7; A7→tests in each task. B1–B5→Part B. ✓
- **Placeholders:** none — every code step shows real code; the only deliberately-deferred decision is B1 (licence), flagged as a user decision. ✓
- **Type consistency:** `Region.code/name/centroid`, `classify()`, `Document.region_code`, `Filters.region`, `RegionStat(code,name,document_count)`, `region_breakdown()`, `GeoView`/`RegionCell`/`build_geo_view`, `SiteContext.geo` are used identically across tasks. ✓
- **Map asset refinement:** A5's "boundary SVG" is implemented as a self-authored **tile-grid** choropleth — still a self-hosted inline SVG choropleth, no third-party asset to licence, even more clearly non-operational. Flagged for the user.
