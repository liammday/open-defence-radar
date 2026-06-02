"""Application-level query use-case, shared by the CLI and the MCP tool.

Builds the store/embedder/retriever/synthesiser from the environment and runs
one grounded query. Keeping this in one place means the CLI and MCP surfaces
give identical answers.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from datetime import date
from typing import Any

from odr.embed.factory import get_embedder
from odr.retrieve.rerank import get_reranker
from odr.retrieve.retriever import Retriever
from odr.store.sqlite_store import SqliteStore
from odr.synthesise.factory import get_generator
from odr.synthesise.synthesiser import Synthesiser
from odr.types import Answer, Filters


def build_filters(
    date_from: str | None = None,
    date_to: str | None = None,
    sources: Sequence[str] | None = None,
    region: str | None = None,
) -> Filters | None:
    """Parse interface-layer strings into Filters (or None when nothing is set)."""
    if not (date_from or date_to or sources or region):
        return None
    return Filters(
        date_from=date.fromisoformat(date_from) if date_from else None,
        date_to=date.fromisoformat(date_to) if date_to else None,
        sources=tuple(sources) if sources else None,
        region=region or None,
    )


def answer_query(topic: str, k: int = 8, filters: Filters | None = None) -> Answer:
    embedder = get_embedder()
    store = SqliteStore(os.environ.get("ODR_DB_PATH", "data/odr.sqlite3"), dim=embedder.dim)
    store.init_schema()
    retriever = Retriever(store, embedder, reranker=get_reranker())
    passages = retriever.retrieve(topic, k=k, filters=filters)
    return Synthesiser(get_generator()).answer(topic, passages)


def answer_to_dict(answer: Answer) -> dict[str, Any]:
    """Serialise an Answer to the interface JSON contract (design §4).

    Shared by the MCP `query` tool and the web `POST /query` route so both
    surfaces emit byte-identical shapes (citations, groundedness, count).
    """
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
