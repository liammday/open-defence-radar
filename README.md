# open-defence-radar

A grounded retrieval engine over **open** defence-and-security signals: it ingests
public open-source data, makes it queryable through AI synthesis where **every
claim is traceable to a cited source**, and exposes the whole thing as an MCP
tool, a web console, and an evaluation/trust dashboard.

> **Open sources only.** This project uses exclusively public, openly-licensed
> data with recorded provenance. It is **analytic, not operational** — awareness
> and analysis of what is publicly known, never targeting or operational content.
> No employer-connected data. No secrets in the repo. See
> [`docs/process/versioning-and-release.md`](docs/process/versioning-and-release.md)
> for the full guardrail checklist.

## Status

In development — **Phase 0 (v0.1.0)**: the end-to-end slice. See the
[milestones](https://github.com/liammday/open-defence-radar/milestones) and the
design docs in [`docs/`](docs/).

## How to run

> Phase 0 is in progress; ingest, query, and the MCP tool land across issues
> #11–#18. The scaffold below runs today.

```bash
# 1. install (uv-managed, pinned lockfile)
uv sync

# 2. configure (copy and fill in — at minimum ANTHROPIC_API_KEY for synthesis)
cp .env.example .env

# 3. CLI entry point
uv run odr --help
uv run odr version
```

Embeddings default to a **local** model (no key, no cost), so a clean clone runs
with only `ANTHROPIC_API_KEY` set. Hosted embedding providers are swappable via
`ODR_EMBEDDER` (see `.env.example`).

## Layout

```
src/odr/
  sources/      one module per open source + a base interface
  ingest/       fetch, normalise, dedupe, schedule entrypoints
  store/        vector + relational + keyword interfaces and impls
  embed/        embeddings provider interface (swappable)
  retrieve/     semantic + keyword + rerank + filters
  synthesise/   grounded answer + citation assembly + verification
  mcp_server/   MCP tool definitions (the `query` tool)
  eval/         question set, scorers, runner
  web/          FastAPI console + trust dashboard
docs/           design + system + frontend specs, process
tests/          pytest, including the eval suite
data/           local stores (gitignored), sample fixtures
```

## Docs

- [Design](docs/superpowers/specs/2026-06-01-open-defence-radar-design.md) — scope + decisions
- [System design](docs/design/system-design.md) — backend architecture
- [Frontend design](docs/design/frontend-design.md) + [prototype](docs/design/prototype.html)
- [Versioning & release](docs/process/versioning-and-release.md) — the controlled-deployment process

## License

To be decided before public release (MIT vs Apache-2.0) — tracked for v1.0.0.
