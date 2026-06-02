"""MCP server exposing the engine as a callable `query` tool (the headline surface).

Read-only. Runs over stdio for local MCP clients (e.g. Claude Desktop/Code):

    uv run odr-mcp            # or: python -m odr.mcp_server.server

Set ODR_DB_PATH to your ingested store and ANTHROPIC_API_KEY for synthesis.
"""

from __future__ import annotations

from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from odr.query import answer_query, answer_to_dict, build_filters

mcp = FastMCP("open-defence-radar")


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
    return answer_to_dict(answer_query(topic, k, build_filters(date_from, date_to, sources)))


def main() -> None:
    """Console-script entry point (stdio transport)."""
    load_dotenv()  # pick up GOOGLE_API_KEY etc. from a local .env
    mcp.run()


if __name__ == "__main__":
    main()
