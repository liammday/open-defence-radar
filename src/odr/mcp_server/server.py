"""MCP server exposing the engine as a callable `query` tool (the headline surface).

Read-only. Runs over stdio for local MCP clients (e.g. Claude Desktop/Code):

    uv run odr-mcp            # or: python -m odr.mcp_server.server

Set ODR_DB_PATH to your ingested store and ANTHROPIC_API_KEY for synthesis.
"""

from __future__ import annotations

from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from odr.query import answer_query, build_filters
from odr.types import Answer

mcp = FastMCP("open-defence-radar")


def _answer_to_dict(answer: Answer) -> dict[str, Any]:
    g = answer.groundedness
    return {
        "answer": answer.text,
        "citations": [
            {
                "marker": c.marker,
                "title": c.document_title,
                "source": c.source_name,
                "url": c.url,
                "published_at": c.published_at.isoformat() if c.published_at else None,
            }
            for c in answer.citations
        ],
        "groundedness": {
            "total_claims": g.total_claims,
            "supported": g.supported,
            "unsupported": g.unsupported,
            "score": g.score,
        },
        "retrieved_count": len(answer.retrieved),
    }


@mcp.tool()
def query(
    topic: str,
    k: int = 8,
    date_from: str | None = None,
    date_to: str | None = None,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    """Answer a question grounded ONLY in ingested open-source defence-and-security signals.

    Returns a cited answer (every claim carries a [n] marker), the resolved
    citations (source, url, published date), a groundedness read
    (supported/total claims), and how many passages were retrieved. Open sources
    only; analytic, not operational. Read-only.

    Args:
        topic: The question or topic to research.
        k: How many passages to retrieve (default 8).
        date_from: Only consider records published on/after this YYYY-MM-DD.
        date_to: Only consider records published on/before this YYYY-MM-DD.
        sources: Restrict to these source ids (e.g. ["contracts-finder"]).
    """
    return _answer_to_dict(answer_query(topic, k, build_filters(date_from, date_to, sources)))


def main() -> None:
    """Console-script entry point (stdio transport)."""
    load_dotenv()  # pick up GOOGLE_API_KEY etc. from a local .env
    mcp.run()


if __name__ == "__main__":
    main()
