# Project brief: open-defence-radar

**Repo name:** `open-defence-radar` (open-source defence signal engine)
**Prepared:** 2026-06-01
**Owner:** Liam Day
**Audience:** Claude Code (build agent)
**Purpose:** A portfolio project that builds and qualifies Applied AI / FDE skills (RAG, MCP, AI APIs, multiple data stores, evaluation) on a defence-and-AI domain, using only open data so it is safe to publish.

---

## 1. Why this project exists

Liam has proven consumer, mobile, Swift, UX/UI, AI-paired development, open-data and geospatial skills through shipped iOS work. The gap is the Applied AI / Forward Deployed Engineer stack: he is a heavy *user* of AI products but has not *built* much with AI APIs, retrieval-augmented generation (RAG), the Model Context Protocol (MCP), or production-style data stores and evaluation.

This project closes that gap with one coherent build. It does the thing an FDE actually does on the job: take messy, real-world, open-source data, make it queryable and grounded through AI, and expose it through a clean interface. The domain (open defence and security signals) doubles as an interview talking point for the AI-and-defence sectors Liam is targeting.

### Skills this is designed to evidence

| Capability | Where it shows up |
|---|---|
| RAG retrieval (semantic + keyword, reranking) | Retrieval layer |
| MCP server design | Tool interface |
| AI API integration (embeddings + generation) | Embedding + synthesis |
| Multiple data stores (vector + relational) | Storage layer |
| Grounding / hallucination control | Cited synthesis |
| AI evaluation rigour | Eval harness |
| Agentic decomposition | MCP client demo |
| Python data pipelines / ETL | Ingest layer |

The single most differentiating element is the **evaluation and grounding layer**. Anyone can wire an LLM to a vector store; measuring retrieval hit-rate and unsupported-claim rate, and shipping the whole thing as a reusable MCP tool an agent can decompose against, is the judgement the FDE feedback flagged as missing.

---

## 2. Guardrails (non-negotiable)

Treat them as hard requirements, not preferences.

1. **Open data only.** Every source must be publicly available with a clear provenance record stored alongside ingested content. No paywalled, leaked, or access-controlled data. No scraping behind logins.
2. **Visible provenance.** Every answer cites its sources. The repo README states "open sources only" explicitly. This reinforces the clearance-aware signal rather than undercutting it.
3. **Nothing employer-connected.** No data, code, credentials, or IP from any current/former employer. No resemblance to internal systems.
4. **Analytic, not operational.** Framing is awareness and analysis (what was announced, what is public). Never targeting, ISTAR tradecraft, or anything that reads as operational planning.
5. **No clearance specifics in public surfaces.** The public repo and any write-up use generic "security cleared" language only. Never name clearance levels, operations, or deployment locations.
6. **Secrets stay out of the repo.** API keys via environment variables and a `.env.example`. Never commit real keys.

---

## 3. Architecture overview

A linear pipeline from open sources to grounded answers, exposed through an MCP server and a small web console.

```
Open sources
  -> Ingest & normalise (scheduled jobs, common schema)
  -> Chunk & embed (AI embeddings API)
  -> Hybrid store (vector for semantics + relational for facts/filters)
  -> Retrieve & rerank (semantic + keyword, optional geo/date filters)
  -> Grounded synthesis (answer only from retrieved passages, every claim cited)
  -> MCP server (the engine as a callable tool)
  -> Eval harness (scores retrieval hit-rate and groundedness on every change)
```

### Surfaces it presents

1. **MCP tool inside an LLM client** (e.g. Claude). A `query` tool that takes a topic plus optional date/geo filters and returns a grounded, cited answer. This is the headline deliverable.
2. **Web query console.** A minimal page: a search box, an answer with inline source markers, a groundedness read, and filter controls.
3. **Eval / trust dashboard.** Retrieval hit-rate, groundedness score, unsupported-claim rate, refreshed on each commit.

---

## 4. Tech stack (Python-first)

Default to Python across ingest, embeddings, retrieval, synthesis, and the MCP server. Keep the web console thin.

- **Language:** Python 3.12+.
- **Package/deps:** `uv` (or `pip` + `venv` if simpler) with a pinned lockfile.
- **MCP server:** the official Python MCP SDK (FastMCP-style). See the `mcp-builder` skill for patterns.
- **Embeddings + generation:** a hosted AI API. Make the provider swappable behind a thin interface so it is not locked to one vendor. Anthropic for generation is the natural choice given the audience; embeddings can come from any hosted embeddings endpoint. Read keys from env.
- **Vector store:** start with a local, file-backed option for v0 (Chroma or `sqlite-vec`/FAISS). Design the storage interface so it can move to `pgvector` on Postgres later without rewriting callers.
- **Relational store:** SQLite for v0 (documents, sources, metadata, ingest log), with a clean path to Postgres.
- **Ingest scheduling:** plain scheduled scripts / cron-style entrypoints for v0; do not over-engineer with a workflow engine.
- **Web console:** a single lightweight Python-served page (FastAPI + a minimal HTML/JS front end). No heavy SPA. A TypeScript/React console is explicitly out of scope for now.
- **Testing:** `pytest`. The eval harness is its own module, runnable in CI.
- **Quality gates:** `ruff` (lint+format) and `mypy` where it pays off.

> Decision recorded: Python-first, thin web console, no separate TS front end. Geospatial is an optional later phase, not core.

---

## 5. Open data sources

All public. Confirm each is reachable and licence-appropriate during the first ingest phase; record the licence and access method per source. Start with two or three, not all of them.

- **UK Contracts Finder** and **Find a Tender** — government procurement notices and award data, with open APIs. Primary source for "who won what" defence-and-AI spend signals.
- **GOV.UK / MoD news and announcements** — public press releases and policy via published feeds.
- **NATO** — public news and press releases.
- **ACLED** (Armed Conflict Location & Event Data) — open conflict-event dataset, useful later for the geospatial stretch. Check the access tier and attribution terms.
- **GDELT** — open global event/news dataset; high volume, good for breadth. Optional.
- **RUSI / open think-tank commentary** — publicly published analysis articles for context. Respect each site's terms; prefer official feeds over scraping.

For each source, store: name, URL, access method, licence/attribution, last-fetched timestamp, and a content hash for dedupe.

---

## 6. Phased build plan

Sequenced so there is a working end-to-end thing early, then depth.

### Phase 0 — v0, end to end (weekend-sized)
Goal: one source in, one grounded cited answer out, callable as an MCP tool.

- Pick **one** source (suggest Contracts Finder).
- Ingest a bounded slice; normalise into the relational store.
- Chunk, embed, write to a local vector store.
- Simple retrieval (top-k semantic) and a grounded-synthesis prompt that answers only from retrieved chunks and returns citations.
- Wrap `query(topic, date_range?)` as an MCP tool.
- A README with the guardrails and a "how to run" section.
- Acceptance: from a fresh clone with keys set, an MCP client can ask a question and get a cited answer drawn from real ingested data.

### Phase 1 — retrieval quality + hybrid store
- Add keyword/BM25 retrieval and a reranking step; combine with semantic.
- Add date and source filters backed by the relational store.
- Add a second and third source with the common schema.
- Dedupe via content hash; incremental re-ingest.

### Phase 2 — evaluation harness
- A curated question set with known-good source documents.
- Metrics: retrieval hit-rate, groundedness (claims supported by retrieved text), unsupported-claim rate.
- Runnable via `pytest` and in CI; output a small scores artefact the dashboard reads.
- This phase is the differentiator. Do not skip or rush it.

### Phase 3 — web console + trust dashboard
- FastAPI page: search box, cited answer, groundedness read, filters.
- Dashboard view rendering the latest eval scores.

### Phase 4 — agentic decomposition demo
- A short example MCP client / agent that takes a harder question, decomposes it across multiple `query` calls (e.g. by source or sub-topic), and recombines into one cited brief. This directly rehearses the decomposition skill the FDE feedback called out.

### Phase 5 (optional stretch) — geospatial "ask the map"
- Add geocoding to events (ACLED) and a geofilter to retrieval ("events within Nkm of a place").
- A simple map surface on the console.
- Leans on Liam's existing geospatial strength; only start once Phases 0-3 are solid.

---

## 7. Suggested repository layout

```
open-defence-radar/
  README.md              guardrails, what it is, how to run
  pyproject.toml         deps + tooling config
  .env.example           required keys, no real values
  src/odr/
    sources/             one module per open source + a base interface
    ingest/              fetch, normalise, dedupe, schedule entrypoints
    store/               vector + relational interfaces and impls
    embed/               embeddings provider interface (swappable)
    retrieve/            semantic + keyword + rerank + filters
    synthesise/          grounded answer + citation assembly
    mcp_server/          MCP tool definitions
    eval/                question set, scorers, runner
    web/                 FastAPI app + minimal console + dashboard
  tests/                 pytest, including the eval suite
  data/                  local stores (gitignored), sample fixtures
```

Keep interfaces (store, embeddings, source) abstract enough that v0's local choices can be swapped for Postgres/pgvector and a hosted vector DB without touching callers.

---

## 8. Definition of done

- Runs from a clean clone with documented env vars; no secrets in the repo.
- At least three open sources ingested with recorded provenance.
- Hybrid retrieval (semantic + keyword + rerank) with date/source filters.
- Grounded synthesis where every claim carries a citation to a retrieved passage.
- MCP server exposing the `query` tool, verified working in an MCP client.
- Eval harness producing retrieval hit-rate, groundedness, and unsupported-claim metrics, wired into CI.
- Web console and trust dashboard live.
- README stating the open-data-only guardrail and provenance approach.
- Public repo, clean commit history, sensible licence.

---

## 9. Notes for the build agent

- Build the smallest end-to-end slice first (Phase 0). Do not build all sources or a perfect store before anything works.
- Favour clarity over cleverness; this is a portfolio piece read by interviewers.
- Treat the guardrails in section 2 as acceptance criteria, not suggestions.
- The `mcp-builder` skill has MCP server patterns; lean on it for the tool layer.
- Record any source whose licence or access terms are unclear, and skip it rather than guess.
