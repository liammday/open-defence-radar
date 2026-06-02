"""Agentic decomposition via the live MCP `query` tool (a real MCP client).

Spawns `odr-mcp` over stdio, plans sub-questions, calls the `query` tool once per
sub-question, then recombines using the same orchestrator logic as the CLI.

    uv run python examples/agent_via_mcp.py \
        "Which UK defence contracts and MoD announcements mention AI or autonomy?"

Needs a generator configured (e.g. LM Studio) and an ingested store.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from odr.agent.orchestrator import decompose_and_answer
from odr.agent.planner import FakePlanner, LLMPlanner
from odr.types import Answer, Citation, Filters, GroundednessReport


def _answer_from_tool(payload: dict[str, Any]) -> Answer:
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

    def query_fn(topic: str, k: int, filters: Filters | None) -> Answer:
        return answers[topic]

    brief = decompose_and_answer(question, planner=FakePlanner(subs), query_fn=query_fn)
    print(brief.text)
    print("\nSources:")
    for c in brief.citations:
        print(f"  {c.marker} {c.source_name} — {c.url}")


if __name__ == "__main__":
    asyncio.run(
        main(sys.argv[1] if len(sys.argv) > 1 else "Which UK defence contracts mention AI?")
    )
