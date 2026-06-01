"""Load the reproducible eval fixtures: a fixed corpus + a curated question set.

The eval runs against these committed fixtures (not the live network), so scores
are deterministic and comparable across commits.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any

from odr.embed.base import Embedder
from odr.ingest.chunk import WholeRecordChunker
from odr.store.base import Store
from odr.types import Document, Filters

_FIXTURES = Path(__file__).parent / "fixtures"


@dataclass(frozen=True)
class Question:
    question: str
    relevant_doc_ids: tuple[str, ...]
    filters: Filters | None = None
    must_mention: tuple[str, ...] = ()


def _to_date(value: Any) -> date | None:
    return date.fromisoformat(value) if value else None


def load_corpus(path: Path | None = None) -> list[Document]:
    raw = json.loads((path or _FIXTURES / "corpus.json").read_text(encoding="utf-8"))
    return [
        Document(
            source_id=r["source_id"],
            source_ref=r["source_ref"],
            title=r["title"],
            url=r["url"],
            text=r["text"],
            content_hash=sha256(r["text"].encode("utf-8")).hexdigest(),
            published_at=_to_date(r.get("published_at")),
        )
        for r in raw
    ]


def load_questions(path: Path | None = None) -> list[Question]:
    raw = json.loads((path or _FIXTURES / "questions.json").read_text(encoding="utf-8"))
    questions: list[Question] = []
    for q in raw:
        f = q.get("filters")
        filters = (
            Filters(
                date_from=_to_date(f.get("date_from")),
                date_to=_to_date(f.get("date_to")),
                sources=tuple(f["sources"]) if f.get("sources") else None,
            )
            if f
            else None
        )
        questions.append(
            Question(
                question=q["question"],
                relevant_doc_ids=tuple(q["relevant_doc_ids"]),
                filters=filters,
                must_mention=tuple(q.get("must_mention", [])),
            )
        )
    return questions


def seed_store(store: Store, embedder: Embedder, corpus: list[Document] | None = None) -> None:
    """Populate a store from the corpus (chunk + embed) for deterministic eval."""
    chunker = WholeRecordChunker()
    for doc in corpus if corpus is not None else load_corpus():
        doc_id = store.upsert_document(doc)
        chunks = chunker.chunk(doc_id, doc)
        vectors = embedder.embed([c.text for c in chunks])
        store.upsert_chunks(doc_id, chunks, vectors, embedder.model_id)
