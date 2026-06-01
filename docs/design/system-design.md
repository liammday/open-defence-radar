# open-defence-radar — System Design

**Date:** 2026-06-01
**Status:** Draft for review
**Builds on:** `docs/superpowers/specs/2026-06-01-open-defence-radar-design.md`

Backend architecture: interfaces, data model, the MCP `query` contract,
retrieval/synthesis internals, the eval harness, error handling, and trade-offs.
Code sketches are illustrative signatures, not final.

---

## 1. Requirements

### 1.1 Functional

| ID | Requirement | Phase |
|---|---|---|
| FR1 | Ingest open-source records into a common `Document` model with provenance | 0 |
| FR2 | Chunk + embed documents; persist vectors + relational metadata in a hybrid store | 0 |
| FR3 | Retrieve relevant passages for a query (semantic; then hybrid + filters) | 0 / 1 |
| FR4 | Synthesise a grounded answer citing only retrieved passages; verify citations | 0 |
| FR5 | Expose `query(topic, filters)` as an MCP tool | 0 |
| FR6 | Web console: search → cited answer + groundedness read + filters | 3 |
| FR7 | Eval harness: retrieval hit-rate, groundedness, unsupported-claim rate; CI-gated | 2 |
| FR8 | Agentic decomposition demo (multi-call → one cited brief) | 4 |
| FR9 | Geospatial filter + map surface | 5 (opt) |

### 1.2 Non-functional

- **Scale:** bounded corpus. Phase 0/1 realistically 10³–10⁴ chunks. `sqlite-vec`
  brute-force KNN is linear and fine to ~10⁵ vectors — **documented ceiling**;
  beyond it → pgvector + ANN index.
- **Latency:** interactive query target a few seconds end-to-end (retrieval in
  ms, generation dominates). Embedding is batch/offline at ingest.
- **Availability:** not a production service in v0 (local/container). No HA.
- **Cost:** minimise. Local embeddings = £0. Generation = Anthropic tokens only.
  Eval in CI bounded by a small curated set + cheap judge model + result caching.
- **Reproducibility:** runs from a clean clone; deterministic where possible
  (RRF and embeddings deterministic; generation pinned to `temperature=0`).
- **Security/guardrails:** open data only, provenance recorded, no secrets
  (design doc §3).
- **Maintainability:** typed `Protocol` interfaces, focused modules, `pytest`.

### 1.3 Constraints

Solo developer; portfolio timeline (Phase 0 weekend-sized); Python 3.12+;
`uv`-managed; `ruff` + `mypy` quality gates.

---

## 2. High-level design

Modules map 1:1 to the repo layout (design doc §5.6). Each is a unit with one
clear job and a typed interface.

```
            ┌─────────┐   fetch/normalise   ┌──────────┐  chunk+embed  ┌──────────┐
 open APIs →│ sources │ ──────────────────→ │  ingest  │ ────────────→ │  store   │
            └─────────┘                     └──────────┘               │ (SQLite: │
                                                  │ embed[]            │ rel +    │
                                            ┌──────────┐               │ vec +    │
                                            │  embed   │←──────────────│ fts)     │
                                            └──────────┘   query vec   └──────────┘
                                                                            ▲
 MCP client ─┐                          ┌──────────┐   passages   ┌──────────┐
 web console ─┼─ query(topic,filters) → │ retrieve │ ───────────→ │synthesise│→ Answer
 agent demo  ─┘                         └──────────┘              │(grounded)│  (+cites,
                                                                  └──────────┘  groundedness)
                                            ┌──────────┐
                                            │   eval   │ reads store + runs queries → metrics JSON
                                            └──────────┘
```

**Composition root:** a small factory layer reads env (`ODR_EMBEDDER`,
`ODR_GENERATOR`, `ODR_DB_PATH`) and constructs concrete `Store` / `Embedder` /
`Generator`, injected into `Retriever`, `Synthesiser`, the MCP server, and the
web app. No module instantiates a provider directly — keeps everything swappable
and testable with fakes.

**CLI:** a thin `odr` CLI (Typer) — `odr ingest <source>`, `odr query "<topic>"`,
`odr eval run`, `odr serve` — so every capability is runnable without the MCP
client or web layer (and scriptable for cron + CI).

---

## 3. Data model (SQLite v0)

```
source            document                     chunk                 chunk_vec (vec0 virtual)
─────────         ───────────────────          ─────────────         ───────────────────────
id (pk)           id (pk)                       id (pk)               rowid ↔ chunk.id
name              source_id (fk → source)       document_id (fk)      embedding float[DIM]
url               source_ref  (e.g. OCDS OCID)  ordinal
access_method     title                         text                  chunk_fts (FTS5, P1)
licence           url                           token_count           ───────────────────────
attribution       published_at (date)           embedding_model       content over chunk.text
enabled           fetched_at (ts)                                     (BM25 ranking)
                  content_hash   ── dedupe
                  text           ── normalised  ingest_run
                  raw (json)     ── original    ───────────
                  UNIQUE(source_id, source_ref) id, source_id, started_at, finished_at,
                  INDEX(content_hash)           status, docs_seen, docs_new,
                  INDEX(published_at)           docs_updated, error
```

- **Provenance chain:** answer → `Citation` → `chunk` → `document`
  (url, published_at, content_hash, fetched_at) → `source` (licence,
  attribution). Every claim is traceable to a fetched, hashed, licensed record.
- **`embedding_model` on `chunk`** lets us detect stale vectors when the embedder
  is swapped (re-embed only mismatches).
- **`chunk_vec`** is the `sqlite-vec` `vec0` virtual table; we maintain a
  rowid↔chunk.id mapping. **`chunk_fts`** is FTS5 (Phase 1) for BM25 keyword
  search — same file, no extra service.
- **Eval results are NOT a table** — they are a versioned JSON artifact
  (`data/eval/latest.json` + timestamped history) so they are diffable in PRs and
  read directly by the dashboard. SQLite stays the *corpus* store only.
- **WAL mode** enabled for read-during-write (serving while a background
  re-ingest runs).

---

## 4. Interfaces (the seams)

```python
# domain types (frozen dataclasses)
Document(source_id, source_ref, title, url, published_at, text, content_hash, raw=None)
Chunk(document_id, ordinal, text, token_count)
ScoredChunk(chunk_id, document_id, text, score, source_name, url, published_at)  # joined for citation
Citation(marker, chunk_id, document_title, source_name, url, published_at)
Filters(date_from=None, date_to=None, sources=None)
Answer(text, citations, groundedness, retrieved)

class Source(Protocol):            # one per open source
    id: str; name: str; licence: str
    def fetch(self, since: date | None, limit: int | None) -> Iterator[RawRecord]: ...
    def normalise(self, raw: RawRecord) -> Document: ...      # also computes content_hash

class Embedder(Protocol):          # LocalEmbedder | VoyageEmbedder | OpenAIEmbedder
    model_id: str; dim: int
    def embed(self, texts: list[str]) -> list[Vector]: ...    # batched

class Generator(Protocol):         # AnthropicGenerator (default)
    model_id: str
    def generate(self, system: str, user: str, *, max_tokens: int, temperature: float = 0.0) -> str: ...

class Store(Protocol):
    def upsert_document(self, doc: Document) -> str: ...       # returns document_id; transactional with its chunks
    def upsert_chunks(self, document_id: str, chunks: list[Chunk], vectors: list[Vector], model_id: str) -> None: ...
    def content_hash_exists(self, content_hash: str) -> bool: ...
    def semantic_search(self, query_vec: Vector, k: int, filters: Filters | None) -> list[ScoredChunk]: ...
    def keyword_search(self, query: str, k: int, filters: Filters | None) -> list[ScoredChunk]: ...   # P1
    def record_ingest_run(self, run: IngestRun) -> None: ...

class Chunker(Protocol):           # WindowChunker (prose) | WholeRecordChunker (short structured)
    def chunk(self, doc: Document) -> list[Chunk]: ...
```

`Retriever(store, embedder)` and `Synthesiser(generator)` are concrete classes
composed over these protocols. Tests inject in-memory fakes for `Store`,
`Embedder`, and `Generator` — no network, no DB, fast.

---

## 5. Ingest / ETL

**Entrypoint:** `odr ingest <source_id> [--since DATE] [--limit N]`.

```
Source.fetch(since=watermark)         # paginated HTTP, retry+backoff
  └─ for each raw record:
       normalise(raw) → Document      # + content_hash
       if content_hash_exists: skip   # exact dedupe
       elif (source_id, source_ref) exists with new hash: update
       else: insert
       Chunker.chunk(doc) → chunks
       Embedder.embed(chunk texts) → vectors   # batched
       Store.upsert_document + upsert_chunks    # one transaction per document
record IngestRun(docs_seen, docs_new, docs_updated, status, error)
```

- **Incremental:** per-source `fetched_at` watermark; `content_hash` dedupe
  absorbs overlap. Re-runs are idempotent.
- **Chunking strategy is per content shape:** structured OCDS procurement records
  are short → `WholeRecordChunker` (usually 1 chunk, preserving field structure
  in the normalised text). GOV.UK/MoD prose → `WindowChunker` (~512-token windows,
  ~64 overlap) using a tokenizer. The `Source` declares its preferred chunker.
- **Scheduling:** a documented cron line / `justfile` target for v0. No workflow
  engine (brief §4).

---

## 6. Retrieval

**Phase 0 — semantic only:**
`embed(query)` → `store.semantic_search(qvec, k)` → join chunk→document→source →
`ScoredChunk` (score = cosine similarity from `sqlite-vec` distance).

**Phase 1 — hybrid + filters:**
```
A = semantic_search(qvec, k1, filters)          # vector
B = keyword_search(query, k2, filters)          # FTS5 BM25
fused = RRF(A, B, K=60)                          # score(d)=Σ 1/(K+rank_i(d)); deterministic
top   = fused[:k]
top   = rerank(query, top)  if ODR_RERANK on     # optional cross-encoder, eval-gated
```
- **Filters** are SQL `WHERE` on the joined `document` (`published_at` range,
  `source_id IN (...)`), applied inside both `semantic_search` and
  `keyword_search` so fusion operates on already-filtered candidates.
- **Reranker** (`bge-reranker`, local) is **off by default and adopted only if the
  eval harness shows it beats RRF** on the curated set — the harness is the
  arbiter, which is the evaluation-rigour story made literal.

---

## 7. Synthesis & grounding

**Prompt shape** (`temperature=0`):
- *System:* answer **only** from the provided passages; every factual claim must
  cite a passage with `[n]`; if passages don't support an answer, say so
  explicitly; do not use outside knowledge.
- *User:* the question + numbered passages, each prefixed
  `[n] (source · date · title) <text>`.

**Two-tier groundedness** — deliberately separated by cost:

| Tier | When | Check | Cost |
|---|---|---|---|
| **Synthesis-time** | every query | each factual sentence has ≥1 `[n]` marker that resolves to a *real* retrieved passage; flag uncited claims + hallucinated citation ids | free (parsing) |
| **Eval-time** | Phase 2, curated set, CI | LLM-judge **entailment**: does the cited passage actually support the claim? | bounded (small set + cheap judge + cache) |

- Synthesis-time catches the cheap failures (uncited claim, citation to a
  passage that wasn't retrieved) on *every* answer and populates
  `Answer.groundedness`.
- Eval-time measures *true* support on a fixed set — the metric that goes in the
  CI gate.
- **v0 limitation (documented):** synthesis-time claim segmentation is heuristic
  (sentence split + factual-sentence heuristic), not a real claim extractor.
  Upgradeable; called out honestly rather than overclaimed.
- **Optional strict mode:** refuse to return an answer whose synthesis-time
  groundedness is below a floor (returns the report + "insufficient grounded
  support" instead of a weakly-grounded answer).

---

## 8. MCP contract

Built with the official Python MCP SDK (FastMCP); see the `mcp-builder` skill
when implementing.

**Tool `query`:**
```jsonc
// input
{
  "topic":     "string (required)",
  "date_from": "YYYY-MM-DD (optional, P1)",
  "date_to":   "YYYY-MM-DD (optional, P1)",
  "sources":   ["source_id", "... (optional, P1)"],
  "k":         "int (optional, default 8)"
}
// output (structured)
{
  "answer": "string with [n] markers",
  "citations": [
    {"marker": "[1]", "title": "...", "source": "...", "url": "...", "published_at": "YYYY-MM-DD"}
  ],
  "groundedness": {"total_claims": 7, "supported": 7, "unsupported": 0, "score": 1.0},
  "retrieved_count": 8
}
```
- **Phase 0:** `topic` (+ `k`). **Phase 1:** adds the filter fields.
- The server composes `query → Retriever → Synthesiser → Answer`, serialised to
  the structured output above. On generation/store failure it returns a
  **structured error**, never a fabricated answer.

---

## 9. Eval harness (Phase 2 — the differentiator)

```
eval/
  questions.yaml   # curated set: {question, filters?, relevant_doc_ids[], must_mention?[]}
  scorers.py       # retrieval hit-rate, recall@k, MRR; groundedness (entailment); unsupported-claim rate
  judge.py         # LLM-judge entailment, temperature 0, stable rubric, cached by hash(claim,passage)
  runner.py        # runs all questions → writes data/eval/latest.json (+ history)
  thresholds.yaml  # floors per metric; ratcheted up, never lowered without a justified PR
```

- **Retrieval hit-rate / recall@k / MRR:** did top-k contain the known relevant
  doc(s)? Pure retrieval quality, no LLM.
- **Groundedness (entailment):** synthesise, then judge each cited claim against
  its passage. `score = supported / total`.
- **Unsupported-claim rate:** claims with no valid support / total.
- **Determinism & cost:** `temperature=0` throughout; judge results cached by
  `(claim, passage)` hash so unchanged pairs aren't re-paid; curated set kept
  small (~15–30 Q) to bound CI token spend (documented envelope).
- **CI gate:** `tests/eval/test_thresholds.py` asserts each metric ≥ its floor;
  a regression past the floor fails the build (design doc §6.2).

---

## 10. Error handling & reliability

| Failure | Handling |
|---|---|
| HTTP fetch 5xx/timeout | retry w/ exponential backoff (`tenacity`); honour rate limits; on exhaustion, fail the `ingest_run` with `error` recorded — don't crash other sources |
| Per-record normalise error | log + skip the record (counted), not fatal |
| Embedding provider error | batch retry; on failure, fail the run cleanly (no partial silent commit) |
| Generation error | retry transient; then MCP/console returns a **structured error**, never a fake answer |
| Partial write crash | one transaction per document (doc + chunks + vectors atomic) → no orphan chunks |
| Low groundedness | surfaced in `Answer.groundedness`; optional strict mode refuses to answer |
| `sqlite-vec` won't load | detected at startup with a clear message + fallback guidance (`pysqlite3-binary`) — verified in the Phase 0 ingest issue |

No silent failures: every fallback either records state (`ingest_run`) or returns
a typed error. (Aligns with the guardrail posture and the `silent-failure-hunter`
review lens.)

---

## 11. Scale & reliability (honest, v0-modest)

- **Vector scale:** `sqlite-vec` brute-force KNN is linear; fine to ~10⁵ vectors.
  Beyond → Postgres + pgvector with HNSW/IVFFlat (the deferred migration; `Store`
  interface unchanged).
- **Concurrency:** single-process FastAPI + SQLite (WAL). Concurrent reads are
  fine; writes serialise; ingest is offline/batch in v0. Documented.
- **Failover:** none in v0 — it's a local/container artifact; "backup" = copy the
  SQLite file. Hosting milestone later adds managed Postgres + object storage.
- **Observability:** structured logs + the `ingest_run` table + the eval
  dashboard ("is it still good?"). No APM in v0.

---

## 12. Trade-offs (explicit)

| Decision | Chose | Gave up | Mitigation |
|---|---|---|---|
| Store | SQLite + `sqlite-vec` (one file) | scale, write concurrency | `Store` interface → pgvector later |
| Embeddings | local default | possible quality headroom | swappable + eval comparison |
| Fusion | RRF (deterministic) | rerank quality | reranker available, eval-gated |
| Groundedness | two-tier (marker + entailment) | single simple metric | cheap check always + accurate check in CI |
| Claim segmentation | heuristic | precision | documented limitation, upgradeable |
| Eval results | JSON artifact | queryable history in DB | diffable in PRs, simpler |

## 13. What I'd revisit as it grows

- Postgres + pgvector + ANN at corpus scale.
- A real claim extractor in place of heuristic sentence segmentation.
- A queue + scheduler if sources grow toward near-real-time.
- A query-result cache for repeated topics.
- Hosting + dev→prod container promotion (the deferred deploy milestone).
