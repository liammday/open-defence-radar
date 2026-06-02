# Final phases — safe geospatial (v0.6.0) → Definition of Done (v1.0.0)

Design for the last two milestones of open-defence-radar: a guardrail-safe
geospatial Phase 5, then the v1.0.0 Definition-of-Done finish and public release.

Status when written: `v0.5.0` (Phase 4 complete). The system already satisfies
DoD §9 items 1–8 (open sources + provenance, hybrid retrieval + filters + rerank,
cited synthesis, MCP `query`, CI-gated eval, web console + trust dashboard +
container, guardrail-stating README). Outstanding: the optional geospatial phase,
a licence, a guardrail sign-off, a clean-clone verification, and the public flip.

## 1. Decision: safe geospatial, not ACLED

The Phase 5 epic (#7) originally proposed ACLED conflict-event geocoding plus
"events within N km of a place" filtering. Two project guardrails rule that out
for a public, clearance-aware repo:

- **Open data only.** The three live sources are OGL v3.0 (UK Gov Open Licence).
  ACLED is a different licensing/attribution regime, not OGL.
- **Analytic, not operational.** Proximity-to-a-place filtering of conflict
  events drifts toward the operational/targeting line the project forbids.

Instead we map the geography **already present** in the OGL procurement data, at a
coarseness that *cannot* be operational.

## 2. What the data supports (ground truth)

Inspected from the 77 live procurement notices in `data/odr.sqlite3`
(Contracts Finder + Find a Tender; GOV.UK/MoD news carries no structured location):

| Signal | Coverage | Meaning |
|---|---|---|
| `tender.items[].deliveryAddresses[].region` | 31/77 (40%) | Where the work is delivered — the analytic signal |
| `parties[].address.region` | 38/77 | Buyer/supplier office region (different meaning) |
| `parties[].address.postalCode` | 77/77 | Precise office postcode — deliberately unused |

Region values are a **mix of names** ("London", "South East") **and NUTS/ITL
codes** ("UKC", "UKL24", "UKI"), all of which normalise to the **12 UK ITL-1
regions** (UKC North East … UKN Northern Ireland).

Design consequences:

- **Altitude = ITL-1 region.** Never finer. This is what makes the feature
  provably analytic: the data contains no point a site could be read from.
- **Delivery region is the signal**, on 40% of notices. We map that and show the
  rest honestly as "region not specified" — consistent with the project's
  visible-provenance ethos. We do **not** reach into office postcodes to inflate
  coverage (precise + wrong meaning).

## 3. Part A — Phase 5 components (v0.6.0)

Each unit has one purpose, a clear interface, and is testable in isolation.

### A1. `odr/geo/regions.py` — ITL-1 gazetteer (pure, no I/O)
- `Region` (frozen): `code` (UKC–UKN), `name`, `centroid: tuple[float, float]`.
- `REGIONS`: the static table of all 12 (names, codes, centroids).
- `classify(value: str) -> Region | None`: accepts a region name, an ITL-1 code,
  or a longer NUTS code truncated to its 3-char ITL-1 prefix ("UKL24" → "UKL");
  case-insensitive; returns `None` for "UK", "England", empty, or unknown.
- Provenance: ITL-1 code↔name and region centroids are ONS open data (OGL v3.0).

### A2. Extract delivery region in the OCDS normaliser
- Add `region_code: str | None = None` to `Document` (`types.py`).
- In `ocds.py:normalise`, read the first non-empty
  `tender.items[].deliveryAddresses[].region`, pass through `classify`, store the
  resulting ITL-1 **code** (or `None`). Persist only the code; name/centroid are
  always derived from the gazetteer (single source of truth).
- `govuk_news.py` and any non-OCDS source: `region_code` stays `None`.

### A3. Store: `region_code` column + backfill
- Schema: `ALTER TABLE document ADD COLUMN region_code TEXT` + an index on it.
  New databases get the column in the `CREATE TABLE`; the migration is additive
  and idempotent (guarded `ADD COLUMN`).
- Persist `region_code` on document insert/update.
- `odr geo backfill` (new CLI subcommand): re-derive `region_code` for existing
  rows from the retained `raw` payload — **no re-fetch**. Idempotent.

### A4. Region geofilter through every surface
- Add `region: str | None = None` to `Filters` (`types.py`); normalise the
  supplied value via `classify` so "South East"/"UKJ" both work.
- `sqlite_store`: add `d.region_code = ?` to the retrieval WHERE when set.
- Surfaces: `odr query --region <value>`, MCP `query` tool `region` param, web
  `/query` `region` field. Coarse equality — analytic by construction.

### A5. Self-hosted SVG region choropleth — on the trust dashboard
- Vendored, simplified **UK ITL-1 regions SVG** (12 region `<path>`s), derived
  from ONS OGL boundaries, provenance + attribution recorded. Lives under
  `odr/web/static` and is served by us — **no external tile server, no runtime
  network call** (consistent with self-hosted fonts #70 and container #72).
- The trust dashboard renders the SVG with each region shaded by its corpus
  notice count via a colourblind-safe sequential ramp, plus:
  - a **text-table fallback** (region, count) for a11y (continues #74), and
  - an explicit **"region not specified: N"** row.
- It is a corpus-wide provenance statistic ("geographic spread of what we've
  ingested, and how much has no stated region"), pairing with the A4 filter.

### A6. Guardrail + provenance
- Record the ONS gazetteer/boundary sources (OGL v3.0 + attribution) in README
  "Sources & licensing". The Phase 5 PR(s) carry the `guardrail` label and run the
  6-point checklist. No new runtime dependency is introduced.

### A7. Tests + CI
- Unit: `classify` (names, ITL-1 codes, NUTS truncation, "UK"/"England"/unknown
  → None); OCDS extraction (fixture → expected code); geofilter (results
  restricted to a region); backfill (raw → region_code).
- The existing eval gate must stay green — the filter must not regress retrieval.

## 4. Part B — v1.0.0 Definition of Done

DoD §9 items 1–8 already met. Remaining:

- **B1. Licence.** Add `LICENSE`, set `pyproject` `license`, update README License
  section. Choice **MIT vs Apache-2.0** is the user's — confirmed at this step.
- **B2. Guardrail review.** Run the 6-point checklist across the whole repo;
  record the sign-off (in the release PR body and/or a `docs/process` note).
- **B3. Clean-clone verification.** Fresh clone → `uv sync` → ruff + mypy + pytest
  + eval all green → bring up console + container → exercise one cited answer and
  one region-filtered query. Capture evidence.
- **B4. Docs polish.** README Status → Phase 5 / v1.0.0; document the geo feature;
  record ACLED + precise/postcode geocoding as deliberately-declined future work
  with the guardrail rationale.
- **B5. Flip public.** Tag `v0.6.0` (Phase 5 milestone) then `v1.0.0` (DoD
  milestone), then make the repo public — **only on the user's explicit go-ahead.**

## 5. Build order

1. Phase 5 ships first as `v0.6.0`: A1 → A2 → A3 → A4 → A5 → A6/A7 (natural
   dependency chain; gazetteer underpins everything).
2. Then v1.0.0 is the closing checklist B1 → B5.

Decomposed against the issue taxonomy: A1 (`area/geo`), A2+A3 (`area/ingest` +
`area/store`, `guardrail`), A4 (`area/retrieve`), A5 (`area/web`, `guardrail`),
A6/B-docs (`area/docs`). The implementation plan focuses on Phase 5; v1.0.0 is a
defined final checklist.

## 6. Out of scope (YAGNI, recorded as declined)

- ACLED and any non-OGL source.
- Precise / postcode / lat-lon point geocoding.
- Sub-region (NUTS-2/3) granularity.
- Interactive tile map (Leaflet/OSM) — rejected for the runtime third-party
  dependency that would see every map view.
- Result-scoped console map (only the current answer's cited regions) — the
  corpus-wide dashboard map is more informative and less coupled; revisit later
  if useful.

## 7. Risks / to verify during build

- **Sourcing the ITL-1 boundary SVG.** Must be OGL and small enough to vendor
  inline. Fallback: a stylised 12-region UK schematic, still OGL-derived, if a
  clean simplified boundary is too heavy. Record whichever is used.
- **Backfill correctness.** Verify `odr geo backfill` reproduces the 40% coverage
  observed in §2 (31 notices with a region) before relying on the map.
- **Filter/eval interaction.** Confirm the region filter does not regress the eval
  thresholds (run the harness after A4).
