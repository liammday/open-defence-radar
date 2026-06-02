# Agentic Decomposition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An `odr agent "<question>"` that decomposes a broad question into sub-questions, runs each through the existing grounded `query`, and recombines them into one cited brief — plus a real-MCP example script.

**Architecture:** A new `src/odr/agent/` package: a `Planner` (LLM-backed, with a `FakePlanner` for tests) produces sub-questions; an orchestrator runs each through an injected `query_fn` (default `answer_query`), owns a deterministic source-split fallback, and recombines into a `Brief` with globally renumbered + deduped citations and aggregated groundedness. No new sources/stores/retrieval.

**Tech Stack:** Python 3.12, Typer (CLI), the existing `Generator`/`answer_query`, `pytest`. Spec: `docs/superpowers/specs/2026-06-02-agentic-decomposition-design.md`.

---

### Task 1: Planner

**Files:**
- Create: `src/odr/agent/__init__.py`
- Create: `src/odr/agent/planner.py`
- Create: `tests/agent/__init__.py`
- Test: `tests/agent/test_planner.py`

- [ ] **Step 1: Create the package inits**

```bash
mkdir -p src/odr/agent tests/agent
printf '"""Agentic decomposition: plan a question into sub-queries, recombine cited answers."""\n' > src/odr/agent/__init__.py
: > tests/agent/__init__.py
```

- [ ] **Step 2: Write the failing tests** — `tests/agent/test_planner.py`

```python
"""Planner: LLM output → a capped, cleaned list of sub-questions."""

from __future__ import annotations

from odr.agent.planner import FakePlanner, LLMPlanner
from odr.synthesise.fake_generator import FakeGenerator


def test_fake_planner_returns_fixed_list() -> None:
    assert FakePlanner(["a", "b"]).plan("anything") == ["a", "b"]


def test_llm_planner_parses_lines() -> None:
    gen = FakeGenerator("What contracts mention AI?\nWhat MoD announcements mention autonomy?")
    subs = LLMPlanner(gen).plan("AI and autonomy across UK defence?")
    assert subs == [
        "What contracts mention AI?",
        "What MoD announcements mention autonomy?",
    ]


def test_llm_planner_strips_bullets_blanks_and_caps_at_max() -> None:
    gen = FakeGenerator("1. a\n- b\n\n  c  \n* d\ne")
    subs = LLMPlanner(gen, max_subs=4).plan("q")
    assert subs == ["a", "b", "c", "d"]


def test_llm_planner_drops_lines_echoing_the_question() -> None:
    gen = FakeGenerator("the question\na real sub-question")
    assert LLMPlanner(gen).plan("the question") == ["a real sub-question"]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/agent/test_planner.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'odr.agent.planner'`

- [ ] **Step 4: Implement** — `src/odr/agent/planner.py`

```python
"""Planning: turn a broad question into focused sub-questions.

`LLMPlanner` uses the configured generator; `FakePlanner` returns a fixed list for
tests (mirrors FakeGenerator / FakeJudge). The planner returns sub-question *strings*
only — the orchestrator owns any filtering and the fallback.
"""

from __future__ import annotations

from typing import Protocol

from odr.synthesise.base import Generator
from odr.synthesise.factory import get_generator

_SYSTEM = (
    "You are a research planner. Break the user's question into 2 to 4 focused, "
    "self-contained sub-questions that together cover it. Output ONE sub-question per "
    "line — no numbering, no bullets, no preamble."
)


class Planner(Protocol):
    def plan(self, question: str) -> list[str]: ...


class FakePlanner:
    """Deterministic planner for tests."""

    def __init__(self, sub_questions: list[str]) -> None:
        self._subs = list(sub_questions)

    def plan(self, question: str) -> list[str]:
        return list(self._subs)


class LLMPlanner:
    def __init__(self, generator: Generator | None = None, max_subs: int = 4) -> None:
        self._generator = generator or get_generator()
        self._max = max_subs

    def plan(self, question: str) -> list[str]:
        out = self._generator.generate(_SYSTEM, question, max_tokens=200, temperature=0.0)
        subs: list[str] = []
        for line in out.splitlines():
            cleaned = line.lstrip("0123456789.)-*• \t").strip()
            if cleaned and cleaned != question.strip():
                subs.append(cleaned)
        return subs[: self._max]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/agent/test_planner.py -q`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add src/odr/agent/__init__.py src/odr/agent/planner.py tests/agent/__init__.py tests/agent/test_planner.py
git commit -m "feat(agent): LLM planner + FakePlanner (#6)"
```

---

### Task 2: Brief type + orchestrator recombination (happy path)

**Files:**
- Modify: `src/odr/types.py` (add `Brief`)
- Create: `src/odr/agent/orchestrator.py`
- Test: `tests/agent/test_orchestrator.py`

- [ ] **Step 1: Write the failing test** — `tests/agent/test_orchestrator.py`

```python
"""Orchestrator: run sub-questions through a query fn, recombine into one Brief."""

from __future__ import annotations

from datetime import date

from odr.agent.orchestrator import decompose_and_answer
from odr.agent.planner import FakePlanner
from odr.types import Answer, Citation, Filters, GroundednessReport, ScoredChunk


def _answer(text: str, cites: tuple[Citation, ...], n_retrieved: int) -> Answer:
    retrieved = tuple(
        ScoredChunk(f"c{i}", f"d{i}", "T", "…", 0.5, "Src", "https://x") for i in range(n_retrieved)
    )
    supported = len(cites)
    return Answer(
        text=text,
        citations=cites,
        groundedness=GroundednessReport(total_claims=supported, supported=supported, unsupported=0),
        retrieved=retrieved,
    )


def _cite(marker: str, url: str) -> Citation:
    return Citation(marker, "ch", "Title " + url, "Source", url, date(2026, 1, 1))


def test_recombines_renumbers_and_dedupes_citations() -> None:
    a1 = _answer("Contracts mention AI [1].", (_cite("[1]", "https://u/a"),), 2)
    a2 = _answer(
        "Tenders cite autonomy [1] and AI [2].",
        (_cite("[1]", "https://u/a"), _cite("[2]", "https://u/b")),  # [1] dupes a1's source
        2,
    )
    responses = {"q1": a1, "q2": a2}

    def query_fn(topic: str, k: int, filters: Filters | None) -> Answer:
        return responses[topic]

    brief = decompose_and_answer("hard q", planner=FakePlanner(["q1", "q2"]), query_fn=query_fn)

    assert brief.sub_questions == ("q1", "q2")
    # global citations: a's url -> [1], b's url -> [2]; a2's local [1] (a's url) deduped to [1]
    assert [c.marker for c in brief.citations] == ["[1]", "[2]"]
    assert [c.url for c in brief.citations] == ["https://u/a", "https://u/b"]
    # a2's text renumbered: local [1]->[1] (same url), local [2]->[2]
    assert "autonomy [1] and AI [2]" in brief.text
    assert brief.question in brief.text
    # aggregated groundedness: 1 + 2 = 3 supported / 3 total
    assert (brief.groundedness.supported, brief.groundedness.total_claims) == (3, 3)


def test_empty_sub_answer_renders_a_note_not_a_fabrication() -> None:
    empty = _answer("", (), 0)
    good = _answer("Found it [1].", (_cite("[1]", "https://u/a"),), 1)
    responses = {"empty": empty, "good": good}

    brief = decompose_and_answer(
        "q",
        planner=FakePlanner(["empty", "good"]),
        query_fn=lambda topic, k, filters: responses[topic],
    )
    assert "No grounded passages matched" in brief.text
    assert [c.marker for c in brief.citations] == ["[1]"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/agent/test_orchestrator.py -q`
Expected: FAIL — `ImportError: cannot import name 'decompose_and_answer'` (and `Brief` missing).

- [ ] **Step 3: Add the `Brief` type** — `src/odr/types.py` (after `Answer`)

```python
@dataclass(frozen=True)
class Brief:
    """A decomposed, recombined answer: sub-questions + one cited brief."""

    question: str
    sub_questions: tuple[str, ...]
    text: str
    citations: tuple[Citation, ...]
    groundedness: GroundednessReport
```

- [ ] **Step 4: Implement the orchestrator** — `src/odr/agent/orchestrator.py`

```python
"""Decompose a question into sub-queries, run each grounded query, recombine.

Recombination is structured and deterministic (no extra synthesis call): citation
markers are renumbered into one global, URL-deduped list; sub-answers with nothing
grounded render a note rather than a fabrication; groundedness is summed.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence

from odr.agent.planner import Planner
from odr.query import answer_query
from odr.types import Answer, Brief, Citation, Filters, GroundednessReport

QueryFn = Callable[[str, int, Filters | None], Answer]

_DEFAULT_SOURCES: tuple[str, ...] = ("contracts-finder", "find-a-tender", "govuk-mod")


def _renumber(text: str, local_to_global: dict[str, str]) -> str:
    return re.sub(r"\[\d+\]", lambda m: local_to_global.get(m.group(0), m.group(0)), text)


def decompose_and_answer(
    question: str,
    *,
    planner: Planner,
    query_fn: QueryFn = answer_query,
    k: int = 8,
    fallback_sources: Sequence[str] = _DEFAULT_SOURCES,
) -> Brief:
    subs = planner.plan(question)
    runs: list[tuple[str, Answer]] = []
    if subs:
        runs = [(sub, query_fn(sub, k, None)) for sub in subs]
    else:  # deterministic source-split fallback
        runs = [
            (f"From {src}", query_fn(question, k, Filters(sources=(src,)))) for src in fallback_sources
        ]

    global_cites: list[Citation] = []
    by_url: dict[str, str] = {}
    sections: list[str] = []
    supported = total = 0

    for label, ans in runs:
        local_to_global: dict[str, str] = {}
        for c in ans.citations:
            marker = by_url.get(c.url)
            if marker is None:
                marker = f"[{len(global_cites) + 1}]"
                by_url[c.url] = marker
                global_cites.append(
                    Citation(
                        marker=marker,
                        chunk_id=c.chunk_id,
                        document_title=c.document_title,
                        source_name=c.source_name,
                        url=c.url,
                        published_at=c.published_at,
                    )
                )
            local_to_global[c.marker] = marker
        grounded = bool(ans.citations or ans.retrieved)
        body = _renumber(ans.text, local_to_global) if grounded else "No grounded passages matched."
        sections.append(f"## {label}\n{body}")
        supported += ans.groundedness.supported
        total += ans.groundedness.total_claims

    text = f"In response to: {question}\n\n" + "\n\n".join(sections)
    return Brief(
        question=question,
        sub_questions=tuple(label for label, _ in runs),
        text=text,
        citations=tuple(global_cites),
        groundedness=GroundednessReport(
            total_claims=total, supported=supported, unsupported=total - supported
        ),
    )
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/agent/test_orchestrator.py -q`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add src/odr/types.py src/odr/agent/orchestrator.py tests/agent/test_orchestrator.py
git commit -m "feat(agent): Brief + recombination orchestrator (#6)"
```

---

### Task 3: Source-split fallback

**Files:**
- Test: `tests/agent/test_orchestrator.py` (add to existing)

- [ ] **Step 1: Write the failing test** — append to `tests/agent/test_orchestrator.py`

```python
def test_falls_back_to_source_split_when_planner_returns_nothing() -> None:
    calls: list[tuple[str, Filters | None]] = []

    def query_fn(topic: str, k: int, filters: Filters | None) -> Answer:
        calls.append((topic, filters))
        return _answer(f"Re {topic} [1].", (_cite("[1]", f"https://u/{len(calls)}"),), 1)

    brief = decompose_and_answer(
        "broad question",
        planner=FakePlanner([]),  # planner yields nothing -> fallback
        query_fn=query_fn,
        fallback_sources=("contracts-finder", "govuk-mod"),
    )

    # one call per fallback source, each filtered to that source, all with the original question
    assert [t for t, _ in calls] == ["broad question", "broad question"]
    assert [f.sources for _, f in calls if f] == [("contracts-finder",), ("govuk-mod",)]
    assert brief.sub_questions == ("From contracts-finder", "From govuk-mod")
    assert len(brief.citations) == 2  # distinct urls, not deduped
```

- [ ] **Step 2: Run to verify it fails (then passes)**

Run: `uv run pytest tests/agent/test_orchestrator.py -q`
Expected: PASS — the Task 2 implementation already covers the fallback branch. (If it fails, fix the orchestrator's `else` branch to match.) This task is a dedicated regression guard for the fallback path.

- [ ] **Step 3: Commit**

```bash
git add tests/agent/test_orchestrator.py
git commit -m "test(agent): guard the source-split fallback (#6)"
```

---

### Task 4: `odr agent` CLI command

**Files:**
- Modify: `src/odr/cli.py`
- Test: `tests/agent/test_cli_agent.py`

- [ ] **Step 1: Write the failing test** — `tests/agent/test_cli_agent.py`

```python
"""`odr agent` CLI smoke — formats a Brief; orchestration is mocked (no model)."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from odr.cli import app
from odr.types import Brief, Citation, GroundednessReport


def test_agent_cli_prints_brief(monkeypatch: pytest.MonkeyPatch) -> None:
    brief = Brief(
        question="Q",
        sub_questions=("sub one", "sub two"),
        text="## sub one\nFinding [1].",
        citations=(Citation("[1]", "ch", "A title", "Contracts Finder", "https://u/1", None),),
        groundedness=GroundednessReport(total_claims=2, supported=2, unsupported=0),
    )
    monkeypatch.setattr("odr.agent.planner.LLMPlanner", lambda *a, **k: object())
    monkeypatch.setattr("odr.agent.orchestrator.decompose_and_answer", lambda *a, **k: brief)

    result = CliRunner().invoke(app, ["agent", "Q"])

    assert result.exit_code == 0
    assert "sub one" in result.output and "sub two" in result.output
    assert "[1]" in result.output and "https://u/1" in result.output
    assert "2/2 claims supported" in result.output
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/agent/test_cli_agent.py -q`
Expected: FAIL — `agent` is not a registered command (exit code 2 / "No such command").

- [ ] **Step 3: Implement the command** — add to `src/odr/cli.py` (after the `query` command)

```python
@app.command()
def agent(
    question: str = typer.Argument(..., help="A broad question to decompose"),
    k: int = typer.Option(8, help="Passages to retrieve per sub-query"),
) -> None:
    """Decompose a broad question across multiple grounded queries into one cited brief."""
    from odr.agent.orchestrator import decompose_and_answer
    from odr.agent.planner import LLMPlanner

    brief = decompose_and_answer(question, planner=LLMPlanner(), k=k)

    typer.echo(f"Sub-questions ({len(brief.sub_questions)}):")
    for sub in brief.sub_questions:
        typer.echo(f"  - {sub}")
    typer.echo("")
    typer.echo(brief.text)
    if brief.citations:
        typer.echo("\nSources:")
        for c in brief.citations:
            published = c.published_at.isoformat() if c.published_at else None
            bits = " · ".join(p for p in (c.source_name, published, c.document_title) if p)
            typer.echo(f"  {c.marker} {bits} — {c.url}")
    g = brief.groundedness
    typer.echo(
        f"\nGroundedness: {g.supported}/{g.total_claims} claims supported (score {g.score:.2f})"
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/agent/test_cli_agent.py -q`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/odr/cli.py tests/agent/test_cli_agent.py
git commit -m "feat(agent): odr agent CLI command (#6)"
```

---

### Task 5: Real-MCP example script

**Files:**
- Create: `examples/agent_via_mcp.py`

(No unit test — like the other example flows, it's exercised manually against a live `odr-mcp` + LM Studio. It reuses the orchestrator's recombination by adapting the MCP tool's dict response into an `Answer`.)

- [ ] **Step 1: Write the script** — `examples/agent_via_mcp.py`

```python
"""Agentic decomposition via the live MCP `query` tool (a real MCP client).

Spawns `odr-mcp` over stdio, plans sub-questions, calls the `query` tool once per
sub-question, and recombines using the same orchestrator logic as the CLI.

    uv run python examples/agent_via_mcp.py "Which UK defence contracts and MoD
    announcements mention AI or autonomy in the last year?"
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from odr.agent.orchestrator import decompose_and_answer
from odr.agent.planner import FakePlanner, LLMPlanner
from odr.types import Answer, Citation, GroundednessReport


def _answer_from_tool(payload: dict) -> Answer:
    """Adapt the MCP `query` tool's dict (design §4 shape) back into an Answer."""
    cites = tuple(
        Citation(
            marker=c["marker"],
            chunk_id="",
            document_title=c["title"] or "",
            source_name=c["source"] or "",
            url=c["url"] or "",
            published_at=date.fromisoformat(c["published_at"]) if c["published_at"] else None,
        )
        for c in payload["citations"]
    )
    g = payload["groundedness"]
    return Answer(
        text=payload["answer"],
        citations=cites,
        groundedness=GroundednessReport(
            total_claims=g["total_claims"], supported=g["supported"], unsupported=g["unsupported"]
        ),
        retrieved=(),  # the tool returns a count, not chunks; recombination keys on citations
    )


async def main(question: str) -> None:
    # Plan synchronously (uses the generator), then fetch each sub-answer over MCP,
    # then recombine with the SAME orchestrator code path as `odr agent`.
    subs = LLMPlanner().plan(question) or [question]
    params = StdioServerParameters(command="uv", args=["run", "odr-mcp"])
    answers: dict[str, Answer] = {}
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        for sub in subs:
            result = await session.call_tool("query", {"topic": sub, "k": 8})
            answers[sub] = _answer_from_tool(result.structuredContent or {})

    brief = decompose_and_answer(
        question, planner=FakePlanner(subs), query_fn=lambda topic, k, filters: answers[topic]
    )
    print(brief.text)
    print("\nSources:")
    for c in brief.citations:
        print(f"  {c.marker} {c.source_name} — {c.url}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "Which UK defence contracts mention AI?"))
```

> The script pre-plans, fetches each sub-answer inside the async MCP session, then reuses `decompose_and_answer` (via a `FakePlanner` holding the already-planned sub-questions) so recombination is identical to the CLI. No nested event loop.

- [ ] **Step 2: Manual check (requires LM Studio + ingested data)**

Run: `uv run python examples/agent_via_mcp.py "Which UK defence contracts and announcements mention AI or autonomy?"`
Expected: prints a recombined brief with renumbered citations. (Skip if LM Studio isn't running — note it in the PR.)

- [ ] **Step 3: Commit**

```bash
git add examples/agent_via_mcp.py
git commit -m "feat(agent): real-MCP decomposition example script (#6)"
```

---

### Task 6: README write-up + full verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a section to `README.md`** (after "Web console + trust dashboard", before "Configuration")

```markdown
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
```

- [ ] **Step 2: Full verification**

Run: `uv run ruff check --fix . && uv run ruff format . && uv run mypy src tests && uv run pytest -q`
Expected: ruff clean, mypy success, all tests pass (including the new agent tests).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(agent): README write-up for odr agent + MCP example (#6)"
```

---

## Release (after all tasks)

Open a PR (`Closes #6` once the sub-issues are filed, or reference the epic), confirm CI (lint·types·tests + e2e) green, squash-merge. The v0.5.0 release (version bump + tag + GitHub Release + guardrail checklist) follows the same flow as v0.4.0 once the epic is closed.
