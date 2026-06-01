# open-defence-radar — Design

**Date:** 2026-06-01
**Status:** Approved (brainstorm)
**Owner:** Liam Day
**Source brief:** `2026-06-01_project-defence-signal-engine.md`

This document is the shared design that the detailed system-design and
frontend-design specs build on, and that the GitHub milestones + issues are
derived from. It records the decisions taken during brainstorming so they are
not re-litigated later.

---

## 1. What this is

An open-source **defence signal engine**: a Retrieval-Augmented Generation (RAG)
pipeline that ingests *public, open* defence-and-security data, makes it
queryable and grounded through an AI synthesis layer, and exposes it as an **MCP
tool**, a **web query console**, and an **evaluation / trust dashboard**.

It is a portfolio piece that evidences the Applied AI / Forward Deployed Engineer
stack — RAG, MCP, AI API integration, multiple data stores, grounding control,
and (the differentiator) **evaluation rigour**.

## 2. Scope of *this* design pass

Decided during brainstorming: **roadmap-all, design Phase 0–1 deep.**

- A full milestone/version roadmap and epic issues for **all six phases**.
- Detailed system-design + frontend-design specs and **build-ready issues for
  Phase 0 and Phase 1 only**.
- Phases 2–5 remain as scoped epics, fleshed out later (via `issues-develop`)
  as their milestone approaches.

## 3. Guardrails (non-negotiable — treated as acceptance criteria)

Carried verbatim in intent from brief §2. Every issue tagged `guardrail` is
checked against these before merge.

1. **Open data only.** Every source publicly available, clear provenance stored
   alongside ingested content. No paywalled, leaked, access-controlled, or
   behind-login data.
2. **Visible provenance.** Every answer cites its sources. README states "open
   sources only" explicitly.
3. **Nothing employer-connected.** No data, code, credentials, or IP from any
   current/former employer. No resemblance to internal systems.
4. **Analytic, not operational.** Awareness and analysis of what is public —
   never targeting, ISTAR tradecraft, or operational planning.
5. **No clearance specifics in public surfaces.** Generic "security cleared"
   language only. Never name levels, operations, or locations.
6. **Secrets stay out of the repo.** Keys via environment variables + a
   `.env.example`. Never commit real keys.

## 4. Decisions locked (brainstorm Q&A)

| Decision | Choice | Why |
|---|---|---|
| Planning depth | Roadmap-all; design P0–1 deep | Fastest path to building with a long-term map |
| Deploy target | Local + container-ready; host later | Zero cost/ops now, minimal clearance-aware surface, still a real deploy artifact to gate on |
| Embeddings default | Local open model; hosted-swappable | Runs from a clean clone with no embeddings key/cost; strong portfolio signal |
| Repo visibility | Private first → public after Phase 0 + guardrail review | Nothing exposed until reviewed |
| Phase 0 source | UK Contracts Finder | Open OCDS API; "who won what" defence-and-AI spend; easy first ingest |
| Phase 1 sources | Find a Tender (FTS) + GOV.UK/MoD news | One more structured OCDS source + one prose source = good schema/retrieval variety |

## 5. System architecture

### 5.1 Pipeline

```
Contracts Finder  (P1: + Find a Tender, + GOV.UK/MoD news)
  → Ingest & normalise   per-source fetcher → common Document schema + provenance row
  → Chunk & embed        local embedding model (default), swappable to Voyage/OpenAI
  → Hybrid store         ONE SQLite file: relational tables + sqlite-vec vectors (+ FTS5 keyword in P1)
  → Retrieve & rerank    P0: top-k semantic · P1: + BM25 keyword + RRF fusion + date/source filters
  → Grounded synthesis   Claude; answer only from retrieved passages; every claim carries a citation
  → Surfaces             MCP `query` tool · FastAPI console · eval harness (CI-gated from P2)
```

### 5.2 Fork 1 — Storage: single SQLite file (relational + `sqlite-vec`)

For v0, the relational store (SQLite) and the vector index (`sqlite-vec`
extension) live in the **same database file**; Phase 1's keyword search comes
free from SQLite's built-in **FTS5/BM25**. The whole knowledge base is one
inspectable file, no server.

- **Rejected — Chroma + SQLite:** standard RAG combo, but two moving parts and a
  weaker single-file story.
- **Rejected (deferred) — Postgres + pgvector from day one:** production-grade,
  but forces a DB server into run-from-clone; heavier than Phase 0 warrants.
- The `Store` interface is identical regardless of backend, so **Postgres +
  pgvector + Postgres FTS is a later milestone, not a rewrite.**
- **Known risk — RESOLVED (#10):** stdlib `sqlite3` on the python.org macOS
  build lacks `enable_load_extension`, and `pysqlite3-binary` ships no arm64
  wheel. The store therefore uses **`apsw`** (bundles a modern SQLite with
  extension loading; cross-platform wheels) to load `sqlite-vec`.

### 5.3 Fork 2 — Provider interfaces: two thin protocols, env-selected

- `Embedder` protocol — default `LocalEmbedder` (fastembed/BGE);
  `VoyageEmbedder`, `OpenAIEmbedder` selectable via `ODR_EMBEDDER`.
- `Generator` protocol — default `AnthropicGenerator` (Claude); selectable via
  `ODR_GENERATOR`.
- Net effect: **Phase 0 needs only `ANTHROPIC_API_KEY`.** Local embeddings mean
  no second key and no embedding cost.
- The eval harness can later quantify local-vs-hosted embedding quality — a
  differentiator, not just plumbing.

### 5.4 Fork 3 — Retrieval fusion (Phase 1): RRF baseline; rerank only if proven

- Phase 0: top-k cosine over `sqlite-vec`.
- Phase 1: add FTS5/BM25 keyword search; fuse with **Reciprocal Rank Fusion**
  (deterministic, model-free); date/source filters via SQL `WHERE` on the
  relational tables.
- A local cross-encoder reranker (e.g. `bge-reranker`) stays **optional, gated
  behind an eval comparison** — the harness decides whether it earns its
  complexity.

### 5.5 Fork 4 — Grounding contract: citation-enforced, verifiable

- Retrieved passages carry stable chunk IDs.
- The synthesis prompt requires every claim to cite a passage ID.
- A post-parse step verifies each citation marker resolves to a real retrieved
  passage and flags uncited claims.
- **Groundedness and unsupported-claim rate are computed mechanically** from
  this, not judged by vibes.

### 5.6 Repository layout (from brief §7, with infra/docs added)

```
open-defence-radar/
  README.md              guardrails, what it is, how to run
  pyproject.toml         deps + tooling config (uv-managed, pinned lockfile)
  .env.example           required keys, no real values (ANTHROPIC_API_KEY at minimum)
  Dockerfile / compose   container-ready (deploy target decision)
  docs/                  design + system + frontend specs, process doc
  src/odr/
    sources/             one module per open source + a base interface
    ingest/              fetch, normalise, dedupe, schedule entrypoints
    store/               vector + relational interfaces and impls (sqlite-vec impl for v0)
    embed/               embeddings provider interface (swappable)
    retrieve/            semantic + keyword + rerank + filters
    synthesise/          grounded answer + citation assembly + verification
    mcp_server/          MCP tool definitions (query tool)
    eval/                question set, scorers, runner
    web/                 FastAPI app + minimal console + dashboard
  tests/                 pytest, including the eval suite
  data/                  local stores (gitignored), sample fixtures
  .github/workflows/     CI: ruff + mypy + pytest (+ eval gate from Phase 2)
```

Interfaces (`Store`, `Embedder`, `Generator`, source base) stay abstract enough
that v0's local choices swap for Postgres/pgvector and hosted providers without
touching callers.

## 6. Milestone versioning & controlled deployment

Adapted from the Peaking process. No Xcode Cloud here; the analog of
internal→external promotion is **CI eval-gate → tagged release → (later)
container dev→prod promotion**.

### 6.1 One milestone = one phase = one minor version

| Milestone | Version | Gate to tag it |
|---|---|---|
| Phase 0 · End-to-end slice | `v0.1.0` | tests green + one cited answer from real Contracts Finder data via MCP |
| Phase 1 · Hybrid retrieval + multi-source | `v0.2.0` | 3 sources ingested + hybrid retrieval + date/source filters |
| Phase 2 · Evaluation harness | `v0.3.0` | eval metrics computed + **wired into CI as a gate** |
| Phase 3 · Web console + trust dashboard | `v0.4.0` | console + dashboard run locally + container builds |
| Phase 4 · Agentic decomposition demo | `v0.5.0` | multi-call decomposition → one cited brief |
| Phase 5 · Geospatial (optional stretch) | `v0.6.0` | geofilter + map surface |
| **Definition of Done** (§9) | `v1.0.0` | all DoD items + guardrail review → **flip repo public** |

### 6.2 The gate has teeth

- **CI gate (every PR):** `ruff` + `mypy` + `pytest` green. **From Phase 2 on,
  the eval harness runs in CI** and must clear threshold floors (retrieval
  hit-rate ≥ target, groundedness ≥ target, unsupported-claim ≤ ceiling) or the
  build fails. A change that regresses retrieval/grounding past the floor cannot
  merge. This is the controlled part — and the portfolio differentiator.
- **Release gate (cut `vX.Y.0`):** milestone 100% closed + CI green on `main` +
  eval thresholds met + **guardrail checklist signed off** (open-data-only,
  provenance recorded, no secrets). Once hosting lands, the tag also promotes the
  container image dev→prod.
- **Flow:** branch → PR → squash-merge to `main` (audit trail) → branch
  protection on `main`.

> Initial eval thresholds are set in Phase 2 from a first measured baseline, then
> ratcheted. They are floors, not targets — the point is *no silent regression*.

## 7. GitHub issues model

Same label vocabulary as Peaking, so the existing `issues-triage`,
`issues-pick-next`, `issues-develop`, and `issues-maintenance` skills work
unchanged.

- **type:** `feature` · `bug` · `enhancement` · `tech-debt` · `idea` · `docs` · `spike`
- **scope/:** `atomic` · `standard` · `large` · `epic`
- **priority/:** `p0` · `p1` · `p2` · `p3`
- **area/:** `ingest` · `sources` · `store` · `embed` · `retrieve` · `synthesise` · `mcp` · `eval` · `web` · `infra-ci` · `docs`
- **status:** `blocked` · `needs-investigation` · `wont-fix` · `stale`
- **`guardrail`** — clearance-aware: any issue touching open-data / provenance /
  secrets, flagged for extra review before merge.

**Epics → sub-issues:**

- Every phase milestone has a `scope/epic` parent issue.
- **Phases 0 & 1:** epics fully decomposed into build-ready sub-issues, each with
  acceptance criteria.
- **Phases 2–5:** epics with a scoped description + a few headline sub-issues,
  decomposed later as the milestone approaches.

## 8. Deliverables of this engagement, in order

1. **This brainstorm design doc** (committed).
2. **System-design spec** (`engineering:system-design`) — interfaces, data
   model, MCP contract, eval harness internals, error handling.
3. **Frontend-design spec** (`frontend-design`) — console + trust dashboard.
4. **Project setup** — create the **private** GitHub repo, push the label scheme,
   7 milestones, 6 epics, granular Phase 0–1 issues wired to milestones, and a
   `CONTRIBUTING`/process doc capturing the versioning + gate. Explicit
   go-ahead required before `gh repo create`.

## 9. Definition of Done (brief §8 — the `v1.0.0` bar)

- Runs from a clean clone with documented env vars; no secrets in the repo.
- ≥3 open sources ingested with recorded provenance.
- Hybrid retrieval (semantic + keyword + rerank) with date/source filters.
- Grounded synthesis where every claim carries a citation to a retrieved passage.
- MCP server exposing the `query` tool, verified in an MCP client.
- Eval harness producing retrieval hit-rate, groundedness, and unsupported-claim
  metrics, wired into CI.
- Web console and trust dashboard live (locally / container).
- README stating the open-data-only guardrail and provenance approach.
- Public repo, clean commit history, sensible licence.

## 10. Open risks / to verify

- ~~`sqlite-vec` extension loading on the target Python (§5.2).~~ Resolved in
  #10 — store uses `apsw`.
- Each source's licence/attribution + access method — verified per-source during
  its ingest issue; record and skip rather than guess (brief §9).
- Local embedding model size/latency on first run (model download) — document in
  README; consider a tiny default model for Phase 0.
- Eval threshold floors are unknowable until Phase 2's first baseline; set then.
