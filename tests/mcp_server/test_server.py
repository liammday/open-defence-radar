"""MCP server: the query tool's structured output (design §8) + registration."""

from __future__ import annotations

import asyncio
from datetime import date

from odr.mcp_server.server import _answer_to_dict, mcp
from odr.types import Answer, Citation, GroundednessReport, ScoredChunk


def test_answer_to_dict_matches_contract() -> None:
    answer = Answer(
        text="The MoD bought AI tooling [1].",
        citations=(
            Citation(
                marker="[1]",
                chunk_id="c1",
                document_title="Doc One",
                source_name="Contracts Finder",
                url="https://example.gov.uk/c1",
                published_at=date(2026, 1, 1),
            ),
        ),
        groundedness=GroundednessReport(total_claims=1, supported=1, unsupported=0),
        retrieved=(
            ScoredChunk(
                chunk_id="c1",
                document_id="d1",
                title="Doc One",
                text="AI tooling",
                score=0.9,
                source_name="Contracts Finder",
                url="https://example.gov.uk/c1",
            ),
        ),
    )
    out = _answer_to_dict(answer)
    assert out["answer"] == "The MoD bought AI tooling [1]."
    assert out["retrieved_count"] == 1
    assert out["groundedness"] == {
        "total_claims": 1,
        "supported": 1,
        "unsupported": 0,
        "score": 1.0,
    }
    assert out["citations"] == [
        {
            "marker": "[1]",
            "title": "Doc One",
            "source": "Contracts Finder",
            "url": "https://example.gov.uk/c1",
            "published_at": "2026-01-01",
        }
    ]


def test_query_tool_is_registered() -> None:
    tools = asyncio.run(mcp.list_tools())
    assert any(t.name == "query" for t in tools)
