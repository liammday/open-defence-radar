"""Eval fixtures load, cross-check, and seed a retrievable store."""

from __future__ import annotations

from odr.embed.fake import FakeEmbedder
from odr.eval.dataset import Question, load_corpus, load_questions, seed_store
from odr.retrieve.retriever import Retriever
from odr.store.memory_store import InMemoryStore


def _corpus_ids() -> set[str]:
    return {f"{d.source_id}:{d.source_ref}" for d in load_corpus()}


def test_corpus_loads_at_least_ten_documents() -> None:
    corpus = load_corpus()
    assert len(corpus) >= 10
    assert "contracts-finder:ai-analysis" in _corpus_ids()


def test_questions_load_and_reference_real_documents() -> None:
    questions = load_questions()
    assert len(questions) >= 10
    assert all(isinstance(q, Question) for q in questions)
    corpus_ids = _corpus_ids()
    for q in questions:  # every relevant id must point at a real corpus doc
        for relevant_id in q.relevant_doc_ids:
            assert relevant_id in corpus_ids, f"{relevant_id} missing from corpus"


def test_seed_store_is_retrievable() -> None:
    embedder = FakeEmbedder(dim=8)
    store = InMemoryStore()
    store.init_schema()
    seed_store(store, embedder)
    assert store.document_count() >= 10
    hits = Retriever(store, embedder).retrieve("counter-drone counter-uas detection", k=5)
    assert any(h.document_id == "find-a-tender:counter-uas" for h in hits)
