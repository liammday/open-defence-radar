"""Ingest pipeline: source -> normalise -> dedupe -> chunk -> embed -> store.

Driven by a FakeSource + FakeEmbedder over both store backends. The live source
+ real model are exercised by a spike, not here.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Mapping
from datetime import date
from typing import Any

import pytest

from odr.embed.fake import FakeEmbedder
from odr.ingest.chunk import WholeRecordChunker
from odr.ingest.pipeline import run_ingest
from odr.sources.base import Source
from odr.store.memory_store import InMemoryStore
from odr.store.sqlite_store import SqliteStore
from odr.types import Document, SourceMeta


class FakeSource:
    def __init__(self, releases: list[dict[str, Any]]) -> None:
        self._releases = releases

    @property
    def meta(self) -> SourceMeta:
        return SourceMeta(
            id="fake-src", name="Fake", url="u", access_method="test", licence="OGL v3.0"
        )

    @property
    def chunker(self) -> WholeRecordChunker:
        return WholeRecordChunker()

    def fetch(
        self, since: date | None = None, limit: int | None = None
    ) -> Iterator[Mapping[str, Any]]:
        yield from (self._releases if limit is None else self._releases[:limit])

    def normalise(self, raw: Mapping[str, Any]) -> Document:
        if raw.get("fail"):
            raise ValueError("boom")
        text = str(raw["text"])
        return Document(
            source_id=self.meta.id,
            source_ref=str(raw["ref"]),
            title="t",
            url="u",
            text=text,
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )


def _requires_source(_s: Source) -> None: ...


def test_fake_source_conforms_to_protocol() -> None:
    _requires_source(FakeSource([]))


@pytest.fixture(params=["memory", "sqlite"])
def pstore(request: pytest.FixtureRequest, tmp_path):  # type: ignore[no-untyped-def]
    if request.param == "memory":
        s: InMemoryStore | SqliteStore = InMemoryStore()
    else:
        s = SqliteStore(tmp_path / "ingest.sqlite3", dim=8)  # match FakeEmbedder(dim=8)
    s.init_schema()
    return s


def test_ingest_new_documents(pstore) -> None:  # type: ignore[no-untyped-def]
    emb = FakeEmbedder(dim=8)
    src = FakeSource(
        [{"ref": "a", "text": "alpha ai contract"}, {"ref": "b", "text": "beta autonomy"}]
    )
    run = run_ingest(src, pstore, emb)
    assert run.docs_seen == 2
    assert run.docs_new == 2
    assert run.docs_updated == 0
    assert run.status == "ok"
    assert pstore.document_count() == 2
    assert pstore.chunk_count() == 2
    assert pstore.get_source("fake-src") is not None
    assert len(pstore.semantic_search(emb.embed(["alpha"])[0], k=1)) == 1


def test_ingest_is_idempotent(pstore) -> None:  # type: ignore[no-untyped-def]
    emb = FakeEmbedder(dim=8)
    run_ingest(FakeSource([{"ref": "a", "text": "alpha"}]), pstore, emb)
    again = run_ingest(FakeSource([{"ref": "a", "text": "alpha"}]), pstore, emb)
    assert again.docs_seen == 1
    assert again.docs_new == 0
    assert again.docs_updated == 0
    assert pstore.document_count() == 1


def test_ingest_updates_changed_content(pstore) -> None:  # type: ignore[no-untyped-def]
    emb = FakeEmbedder(dim=8)
    run_ingest(FakeSource([{"ref": "a", "text": "old"}]), pstore, emb)
    again = run_ingest(FakeSource([{"ref": "a", "text": "new"}]), pstore, emb)
    assert again.docs_updated == 1
    assert again.docs_new == 0
    assert pstore.document_count() == 1


def test_ingest_per_record_error_is_not_fatal(pstore) -> None:  # type: ignore[no-untyped-def]
    emb = FakeEmbedder(dim=8)
    src = FakeSource(
        [{"ref": "a", "text": "ok"}, {"ref": "b", "fail": True}, {"ref": "c", "text": "fine"}]
    )
    run = run_ingest(src, pstore, emb)
    assert run.docs_seen == 3
    assert run.docs_new == 2
    assert run.status == "partial"
    assert run.error
    assert pstore.document_count() == 2


def test_ingest_respects_limit(pstore) -> None:  # type: ignore[no-untyped-def]
    emb = FakeEmbedder(dim=8)
    src = FakeSource([{"ref": str(i), "text": f"text {i}"} for i in range(5)])
    run = run_ingest(src, pstore, emb, limit=2)
    assert run.docs_seen == 2


def test_ingest_records_a_run(pstore) -> None:  # type: ignore[no-untyped-def]
    emb = FakeEmbedder(dim=8)
    run_ingest(FakeSource([{"ref": "a", "text": "x"}]), pstore, emb)
    assert pstore.ingest_run_count() == 1
