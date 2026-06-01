"""Retriever: embed the query, return the store's ranked passages."""

from __future__ import annotations

from odr.embed.fake import FakeEmbedder
from odr.retrieve.retriever import Retriever
from odr.store.memory_store import InMemoryStore
from odr.types import Chunk, Document, ScoredChunk


def _seed(store: InMemoryStore, embedder: FakeEmbedder) -> None:
    for ref, text in {"a": "alpha contract about ai", "b": "beta about autonomy"}.items():
        doc = Document(
            source_id="s", source_ref=ref, title="t", url="u", text=text, content_hash=ref
        )
        doc_id = store.upsert_document(doc)
        store.upsert_chunks(
            doc_id,
            [Chunk(doc_id, 0, text, len(text.split()))],
            vectors=embedder.embed([text]),
            model_id="fake",
        )


def test_retrieve_embeds_query_and_returns_scored_chunks() -> None:
    store, embedder = InMemoryStore(), FakeEmbedder(dim=8)
    store.init_schema()
    _seed(store, embedder)
    hits = Retriever(store, embedder).retrieve("alpha contract about ai", k=2)
    assert len(hits) == 2
    assert hits[0].text == "alpha contract about ai"  # exact-text match is nearest
    assert hits[0].score >= hits[1].score


def test_retrieve_k_limits_results() -> None:
    store, embedder = InMemoryStore(), FakeEmbedder(dim=8)
    store.init_schema()
    _seed(store, embedder)
    assert len(Retriever(store, embedder).retrieve("anything", k=1)) == 1


class _ReverseReranker:
    model_id = "reverse"

    def rerank(self, query: str, chunks: list[ScoredChunk]) -> list[ScoredChunk]:
        return list(reversed(chunks))


def test_retriever_applies_reranker_when_present() -> None:
    store, embedder = InMemoryStore(), FakeEmbedder(dim=8)
    store.init_schema()
    _seed(store, embedder)
    base = Retriever(store, embedder).retrieve("alpha contract about ai", k=2)
    reranked = Retriever(store, embedder, reranker=_ReverseReranker()).retrieve(
        "alpha contract about ai", k=2
    )
    assert [c.chunk_id for c in reranked] == [c.chunk_id for c in reversed(base)]
