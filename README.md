# open-defence-radar

A grounded retrieval engine over **open** defence-and-security signals: it ingests
public open-source data, makes it queryable through AI synthesis where **every
claim is traceable to a cited source**, and exposes the whole thing as an MCP
tool (plus a CLI, and a web console in a later phase).

> **Open sources only.** This project uses exclusively public, openly-licensed
> data with recorded provenance. It is **analytic, not operational** — awareness
> and analysis of what is publicly known, never targeting or operational content.
> No employer-connected data. No secrets in the repo. Full guardrail checklist:
> [`docs/process/versioning-and-release.md`](docs/process/versioning-and-release.md).

## Status

**Phase 2 (`v0.3.0`) — evaluation harness.** Three open sources, hybrid retrieval,
and filters (Phase 1), now with an **evaluation harness** that scores retrieval
hit-rate, groundedness (entailment), and unsupported-claim rate against a fixed
question set — wired into CI as a release gate (`odr eval`). See the
[milestones](https://github.com/liammday/open-defence-radar/milestones) and
[releases](https://github.com/liammday/open-defence-radar/releases).

## How it works

```
Open sources: UK Contracts Finder · Find a Tender · GOV.UK/MoD news (all OGL v3.0)
  → ingest: fetch → normalise → dedupe → chunk → embed (local BGE) → store
  → store: one SQLite file (apsw + sqlite-vec vectors + FTS5 keyword index)
  → retrieve: hybrid — semantic (vector) + keyword (BM25), fused with RRF, + filters
  → synthesise: Claude answers ONLY from retrieved passages, every claim cited
  → surfaces: `odr query` CLI · MCP `query` tool
```

## Quick start

Requires Python 3.12+ and [`uv`](https://docs.astral.sh/uv/).

```bash
# 1. install (pinned lockfile)
uv sync

# 2. configure — for synthesis you need an Anthropic API key.
cp .env.example .env
#   then set ANTHROPIC_API_KEY in .env (or export it).
#   Embeddings default to a LOCAL model (no key, no cost); the ~130 MB model
#   downloads once on first ingest and is cached.

# 3. ingest bounded slices of real open data
#    sources: contracts-finder · find-a-tender · govuk-mod
export ANTHROPIC_API_KEY=sk-ant-...        # or put it in .env
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
      "env": { "ANTHROPIC_API_KEY": "sk-ant-...", "ODR_DB_PATH": "data/odr.sqlite3" }
    }
  }
}
```

The tool returns a cited answer, the citations (source · url · date), a
groundedness read, and the retrieved-passage count.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required for synthesis (the answer step). |
| `ODR_EMBEDDER` | `local` | `local` (offline BGE) · `fake` (tests). |
| `ODR_GENERATOR` | `anthropic` | Generation provider. |
| `ODR_ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Override the synthesis model. |
| `ODR_DB_PATH` | `data/odr.sqlite3` | SQLite store location. |
| `ODR_RERANK` | `0` | `1` enables the cross-encoder reranker (experimental; eval-gated). |

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

Contains public sector information licensed under the Open Government Licence v3.0.

## License

Project licence to be decided before public release (MIT vs Apache-2.0) — tracked
for `v1.0.0`.
