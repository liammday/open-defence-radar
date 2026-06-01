"""Application-level query use-case, shared by the CLI and the MCP tool.

Builds the store/embedder/retriever/synthesiser from the environment and runs
one grounded query. Keeping this in one place means the CLI and MCP surfaces
give identical answers.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from datetime import date

from odr.embed.factory import get_embedder
from odr.retrieve.retriever import Retriever
from odr.store.sqlite_store import SqliteStore
from odr.synthesise.factory import get_generator
from odr.synthesise.synthesiser import Synthesiser
from odr.types import Answer, Filters


def build_filters(
    date_from: str | None = None,
    date_to: str | None = None,
    sources: Sequence[str] | None = None,
) -> Filters | None:
    """Parse interface-layer strings into Filters (or None when nothing is set)."""
    if not (date_from or date_to or sources):
        return None
    return Filters(
        date_from=date.fromisoformat(date_from) if date_from else None,
        date_to=date.fromisoformat(date_to) if date_to else None,
        sources=tuple(sources) if sources else None,
    )


def answer_query(topic: str, k: int = 8, filters: Filters | None = None) -> Answer:
    embedder = get_embedder()
    store = SqliteStore(os.environ.get("ODR_DB_PATH", "data/odr.sqlite3"), dim=embedder.dim)
    store.init_schema()
    passages = Retriever(store, embedder).retrieve(topic, k=k, filters=filters)
    return Synthesiser(get_generator()).answer(topic, passages)
