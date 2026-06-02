# open-defence-radar — Phase 4: agentic decomposition demo

**Date:** 2026-06-02
**Status:** Approved design (brainstormed)
**Milestone:** Phase 4 (`v0.5.0`) · Epic: #6
**Builds on:** the grounded `query` use-case (`odr.query.answer_query`) and the MCP `query` tool.

## 1. Purpose

Rehearse the FDE **decomposition** skill: an agent takes a question too broad for a
single retrieval, **plans** it into focused sub-questions, runs each through the
existing grounded `query`, and **recombines** the results into one cited brief —
without losing provenance. Open-data guardrails are inherited unchanged (every
claim still traces to a fetched, licensed passage).

**Release gate (`v0.5.0`):** multi-call decomposition → one cited brief.

## 2. Architecture

One new package, `src/odr/agent/`, plus a `Brief` value type. It reuses the
existing `Generator` (via `get_generator()`) and the `answer_query` use-case; it
adds **no** new data sources, stores, or retrieval logic.

```
odr agent "<hard question>"
  → Planner.plan(question)            # LLM → sub-questions (deterministic fallback)
  → for each sub-question: query_fn() # the SAME grounded query the CLI/MCP use
  → recombine(sub-answers)            # renumber citations globally, dedupe, aggregate
  → Brief                             # sub-questions + combined cited text + sources
```

Units (each independently testable, communicating through narrow interfaces):

| Unit | File | Responsibility |
|------|------|----------------|
| `Planner` protocol + `LLMPlanner` + `FakePlanner` | `agent/planner.py` | Turn a question into 2–4 topical sub-questions (LLM); empty/unusable output signals the orchestrator to fall back |
| `decompose_and_answer(...)` | `agent/orchestrator.py` | Drive the sub-queries through an injected `query_fn`; own the deterministic source-split fallback; recombine into a `Brief` |
| `Brief` | `types.py` | Frozen value object: `question`, `sub_questions`, `text`, `citations`, `groundedness` |
| `odr agent` | `cli.py` | CLI surface; builds `LLMPlanner` + `answer_query`, prints the brief |
| `agent_via_mcp.py` | `examples/` | Real MCP client: spawns `odr-mcp`, calls the `query` tool per sub-question |

## 3. Decomposition (planner)

- `Planner` is a `Protocol` with `plan(question: str) -> list[str]`.
- `LLMPlanner(generator)` prompts the model: *"Break this question into 2–4 focused,
  self-contained sub-questions, one per line, no numbering."* It parses non-empty
  lines, trims, and caps at 4. Uses `get_generator()` by default (the LM Studio path).
- **Fallback (deterministic), owned by the orchestrator:** if `plan()` returns
  nothing usable (empty, or a single line echoing the question), the orchestrator
  splits by **ingested source** — running the original question once per source via a
  single-source `Filters` — using an injectable source list (defaults to the three
  ingested sources). A live demo therefore always degrades to a valid multi-call run
  rather than erroring. The planner itself only ever returns topical sub-question
  strings; filters are the orchestrator's concern.
- `FakePlanner(sub_questions)` returns a fixed list, mirroring `FakeGenerator` /
  `FakeJudge`, so the orchestrator is tested with no model.

## 4. Recombination (the heart of the demo)

**Structured, deterministic, no extra synthesis call** — chosen so every citation is
preserved exactly and the decomposition is *visible*:

1. Run each sub-question through `query_fn` (default `answer_query`), in order —
   `filters=None` for LLM sub-questions, or a single-source `Filters` for the
   fallback split.
2. Build a **global citation list**: iterate sub-answers' citations, key by `url`,
   assign a global marker in first-seen order (so the same source shared across
   sub-answers gets **one** number); record a `(sub-answer, local marker) → global
   marker` map.
3. **Rewrite** each sub-answer's text, replacing local `[n]` markers with their
   global equivalents.
4. `Brief.text` = a one-line lead + one section per sub-question (the sub-question as
   a heading, then its rewritten grounded answer). A sub-question with no grounded
   passages renders a "no grounded passages matched" note — never a fabricated answer.
5. `Brief.citations` = the deduped global list; `Brief.groundedness` =
   `GroundednessReport(Σ supported, Σ total)` across sub-answers.

*Rejected alternative:* a second synthesis pass fusing all passages into one flowing
brief — more coherent prose, but an extra model call, a second-order grounding step,
and it hides the decomposition. Not worth it for a demo whose point is to *show* the
decomposition.

## 5. Surfaces

- **`odr agent "<question>"`** (`--k`, optional `--date-from/--date-to/--source`
  passthrough): builds `LLMPlanner(get_generator())` + `answer_query`, runs
  `decompose_and_answer`, prints sub-questions → combined brief → numbered sources →
  aggregate groundedness, in the same style as `odr query`.
- **`examples/agent_via_mcp.py`**: an MCP client (via the `mcp` client SDK) that
  spawns `odr-mcp` over stdio, calls the `query` tool once per sub-question, and feeds
  the results through the *same* recombination function — the genuine "MCP client/
  agent" demonstration, written up in the README.

## 6. Testing (TDD)

- **Planner:** `LLMPlanner` parses a fake generator's multi-line output into a capped
  list; whitespace/empty handling; fallback fires (source-split) when output is unusable.
- **Orchestrator:** with a `FakePlanner` + a fake `query_fn` returning canned `Answer`s
  per sub-question, assert: global citation renumbering, cross-sub-answer dedup by URL,
  aggregated groundedness, all sources preserved, empty-sub-answer note. Fully
  deterministic — no model, store, or network.
- **CLI:** a smoke test (`odr agent` wired, prints a brief) using an injected fake.
- The MCP example is exercised manually, like the other example flows.

## 7. Out of scope (YAGNI)

No iterative/multi-round planning (single decomposition pass); no re-ranking across
sub-answers; no agent surface in the web console; no caching of sub-answers; no new
sources or stores. These can be revisited post-`v0.5.0` if warranted.

## 8. Guardrails

Unchanged and inherited: open data only, provenance on every citation, analytic-not-
operational framing, no secrets. The agent adds orchestration only — it never reaches
outside the existing grounded `query`, so it cannot surface anything the engine
couldn't already cite.
