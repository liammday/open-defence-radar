# open-defence-radar

A grounded retrieval engine over **open** defence-and-security signals: it ingests
public open-source data, makes it queryable through AI synthesis where **every
claim is traceable to a cited source**, and exposes the whole thing as an MCP
tool (plus a CLI and a web console).

> **Open sources only.** This project uses exclusively public, openly-licensed
> data with recorded provenance. It is **analytic, not operational** — awareness
> and analysis of what is publicly known, never targeting or operational content.
> No employer-connected data. No secrets in the repo. Full guardrail checklist:
> [`docs/process/versioning-and-release.md`](docs/process/versioning-and-release.md).

## Status

**`v1.0.0` — Definition of Done.** All six phases complete: open sources + recorded
provenance, hybrid retrieval (semantic + keyword + rerank) with date/source/region
filters, grounded synthesis where every claim is cited, an MCP `query` tool, a
CI-gated evaluation harness, the web console + trust dashboard (with a region
choropleth), `odr agent` decomposition, and region-level geospatial. Open data only;
analytic, not operational. Runs from a clean clone (`uv sync` → tests + eval green).
See the [milestones](https://github.com/liammday/open-defence-radar/milestones) and
[releases](https://github.com/liammday/open-defence-radar/releases).

## How it works

```
Open sources: UK Contracts Finder · Find a Tender · GOV.UK/MoD news (all OGL v3.0)
  → ingest: fetch → normalise → dedupe → chunk → embed (local BGE) → store
  → store: one SQLite file (apsw + sqlite-vec vectors + FTS5 keyword index)
  → retrieve: hybrid — semantic (vector) + keyword (BM25), fused with RRF, + filters
  → synthesise: Claude answers ONLY from retrieved passages, every claim cited
  → surfaces: `odr query` CLI · MCP `query` tool · `odr-web` console + dashboard · `odr agent` decomposition
```

## Quick start

Requires Python 3.12+ and [`uv`](https://docs.astral.sh/uv/).

```bash
# 1. install (pinned lockfile)
uv sync

# 2. configure — synthesis uses Gemini's free tier by default.
cp .env.example .env
#   set GOOGLE_API_KEY (free, no card: https://aistudio.google.com/apikey).
#   Embeddings default to a LOCAL model (no key, no cost); the ~130 MB model
#   downloads once on first ingest and is cached.
#   (Prefer Claude? set ODR_GENERATOR=anthropic + ANTHROPIC_API_KEY — pay-per-use.)

# 3. ingest bounded slices of real open data
#    sources: contracts-finder · find-a-tender · govuk-mod
export GOOGLE_API_KEY=...                   # or put it in .env
uv run odr ingest contracts-finder --limit 50
uv run odr ingest find-a-tender --limit 50
uv run odr ingest govuk-mod --limit 50
#    later, fetch only what's new:  uv run odr ingest contracts-finder --incremental

# 4. ask a grounded, cited question (optional date/source filters)
uv run odr query "Which contracts mention AI or autonomy?"
uv run odr query "Recent MoD announcements" --source govuk-mod --date-from 2026-01-01
```

Example output:

```
<a concise answer with inline [1] [2] markers, drawn only from ingested notices>

Sources:
  [1] UK Contracts Finder · 2026-03-14 · <notice title> — https://www.contractsfinder.service.gov.uk/Notice/...
  [2] UK Contracts Finder · 2026-01-28 · <notice title> — https://www.contractsfinder.service.gov.uk/Notice/...

Groundedness: 4/4 claims supported (score 1.00)
```

If nothing has been ingested (or no passage matches), the engine says so rather
than inventing an answer.

## Use it as an MCP tool

The headline surface: a read-only `query` tool inside an MCP client (e.g. Claude
Desktop / Claude Code). Add to your client's MCP config:

```json
{
  "mcpServers": {
    "open-defence-radar": {
      "command": "uv",
      "args": ["run", "odr-mcp"],
      "cwd": "/absolute/path/to/open-defence-radar",
      "env": { "GOOGLE_API_KEY": "...", "ODR_DB_PATH": "data/odr.sqlite3" }
    }
  }
}
```

The tool returns a cited answer, the citations (source · url · date), a
groundedness read, and the retrieved-passage count.

## Web console + trust dashboard

The same grounded `query`, plus the evaluation trust dashboard, served as a small
FastAPI app — the "Open Signals Reading Room":

```bash
uv run odr-web            # → http://localhost:8000
```

The **console** (`/`) renders a grounded brief with inline citation chips that
expand into provenance cards; the **trust dashboard** (`/trust`) shows the eval
metrics (hit-rate, groundedness, unsupported-claim) against their floors plus a
live source-provenance table. `GET /healthz` is a liveness probe. Generation uses
the same provider as the CLI/MCP (`ODR_GENERATOR`), and the fonts are self-hosted,
so the page makes no third-party request.

### In a container

```bash
docker compose up --build    # → http://localhost:8000
```

Compose mounts `./data` (the ingested store + eval artifacts) and points the
container at a local LM Studio / Ollama on the host (`host.docker.internal`).
Ingest + eval still run on the host (`uv run odr ingest …`, `uv run odr eval`),
writing into `./data`, which the container reads.

## Agentic decomposition

For questions too broad for a single retrieval, `odr agent` plans the question into
focused sub-questions, runs each through the same grounded `query`, and recombines
them into **one cited brief** — every claim still traces to a fetched source.

```bash
uv run odr agent "Which UK defence contracts and MoD announcements mention AI or autonomy?"
```

`examples/agent_via_mcp.py` does the same as a real **MCP client** — spawning `odr-mcp`
and calling the `query` tool per sub-question — to rehearse FDE-style decomposition
over the protocol.

## Geospatial

Procurement notices carry a delivery **region**; the ingester normalises it (a region
name or NUTS code) to one of the 12 UK **ITL-1 regions** and stores it on the document.
You can then filter retrieval by region, and the trust dashboard maps where the open
procurement activity is:

```bash
uv run odr query "MoD AI procurement" --region "South East"   # name or ITL-1 code (UKJ)
uv run odr geo backfill                                        # re-derive regions for an existing store
```

**This is deliberately region-level — analytic, not operational.** The source data
contains no point finer than a region, so nothing here can resolve to a site; the
dashboard map is a self-hosted tile-grid choropleth (no external tile server, no
third-party asset), and notices with no stated region are shown honestly as
"region not specified". The richer-but-riskier options (ACLED conflict-event geocoding,
precise/postcode coordinates, "within N km of a place") were **deliberately declined** —
they cut against the open-data-only and analytic-not-operational guardrails for a
clearance-aware public repo.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `GOOGLE_API_KEY` | — | Required for synthesis when `ODR_GENERATOR=gemini` (the default). Free tier. |
| `ANTHROPIC_API_KEY` | — | Required for synthesis when `ODR_GENERATOR=anthropic` (pay-per-use). |
| `ODR_GENERATOR` | `gemini` | `gemini` (free tier) · `anthropic` (pay-per-use) · `lmstudio` (local). |
| `ODR_GEMINI_MODEL` | `gemini-2.0-flash` | Override the Gemini model. |
| `ODR_ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Override the Claude model. |
| `ODR_LLM_BASE_URL` | `http://localhost:1234/v1` | OpenAI-compatible server for `lmstudio` (LM Studio / Ollama). |
| `ODR_LLM_MODEL` | `local-model` | The model id loaded in that server (e.g. `google/gemma-4-e4b`). |
| `ODR_EMBEDDER` | `local` | `local` (offline BGE) · `fake` (tests). |
| `ODR_DB_PATH` | `data/odr.sqlite3` | SQLite store location. |
| `ODR_EVAL_DIR` | `data/eval` | Where the eval artifact (`latest.json`) is read/written. |
| `ODR_RERANK` | `0` | `1` enables the cross-encoder reranker (experimental; eval-gated). |
| `ODR_WEB_HOST` | `127.0.0.1` | `odr-web` bind host (`0.0.0.0` in the container). |
| `ODR_WEB_PORT` | `8000` | `odr-web` bind port. |

## Development

```bash
uv run ruff check . && uv run ruff format --check .   # lint + format
uv run mypy src tests                                  # types
uv run pytest -q                                       # tests (offline)
```

CI runs these gates on every PR (GitHub Actions). "Require status checks" branch
protection turns on at public release.

## Evaluation

The differentiator: quality is measured, not asserted.

```bash
uv run odr eval        # scores the fixture question set; writes data/eval/latest.json
```

`odr eval` runs a fixed question set against a committed fixture corpus and reports
**retrieval hit-rate / recall@k / MRR** and **groundedness** (an LLM judge checks
each cited claim is entailed by its passage) plus the **unsupported-claim rate**.
Floors live in `src/odr/eval/fixtures/thresholds.json` and are enforced in CI
(`tests/eval/test_thresholds.py`) — a metric
breaching its floor fails the build, so retrieval/grounding can't silently regress.

## Docs

- [Design](docs/superpowers/specs/2026-06-01-open-defence-radar-design.md) — scope + decisions
- [System design](docs/design/system-design.md) — backend architecture
- [Frontend design](docs/design/frontend-design.md) + [prototype](docs/design/prototype.html)
- [Versioning & release](docs/process/versioning-and-release.md) — the controlled-deployment process

## Sources & licensing

| Source | Licence | Access |
|---|---|---|
| UK Contracts Finder | Open Government Licence v3.0 | OCDS API |
| Find a Tender | Open Government Licence v3.0 | OCDS API |
| GOV.UK · MoD news | Open Government Licence v3.0 | Search API |
| ONS UK ITL-1 region geography (names, codes, centroids) | Open Government Licence v3.0 | Static gazetteer (`odr/geo`) |

Contains public sector information licensed under the Open Government Licence v3.0.
The dashboard region map is a self-authored tile-grid schematic (no third-party map asset).

## License

[MIT](LICENSE) © Liam Day. The ingested data remains under its own licence (Open
Government Licence v3.0); see [Sources & licensing](#sources--licensing).
