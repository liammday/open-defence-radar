"""MCP server exposing the engine as a callable `query` tool (the headline surface).

Read-only. Runs over stdio for local MCP clients (e.g. Claude Desktop/Code):

    uv run odr-mcp            # or: python -m odr.mcp_server.server

Set ODR_DB_PATH to your ingested store and ANTHROPIC_API_KEY for synthesis.
"""

from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from odr.embed.factory import get_embedder
from odr.retrieve.retriever import Retriever
from odr.store.sqlite_store import SqliteStore
from odr.synthesise.factory import get_generator
from odr.synthesise.synthesiser import Synthesiser
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


def _run_query(topic: str, k: int) -> Answer:
    embedder = get_embedder()
    store = SqliteStore(os.environ.get("ODR_DB_PATH", "data/odr.sqlite3"), dim=embedder.dim)
    store.init_schema()
    passages = Retriever(store, embedder).retrieve(topic, k=k)
    return Synthesiser(get_generator()).answer(topic, passages)


@mcp.tool()
def query(topic: str, k: int = 8) -> dict[str, Any]:
    """Answer a question grounded ONLY in ingested open-source defence-and-security signals.

    Returns a cited answer (every claim carries a [n] marker), the resolved
    citations (source, url, published date), a groundedness read
    (supported/total claims), and how many passages were retrieved. Open sources
    only; analytic, not operational. Read-only.

    Args:
        topic: The question or topic to research.
        k: How many passages to retrieve (default 8).
    """
    return _answer_to_dict(_run_query(topic, k))


def main() -> None:
    """Console-script entry point (stdio transport)."""
    mcp.run()


if __name__ == "__main__":
    main()
