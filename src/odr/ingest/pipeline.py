"""The ingest pipeline — assemble a Source, Store, Embedder, and Chunker.

For each fetched record: normalise → skip if the content hash is already stored
(exact dedupe) → otherwise upsert the document and (re)write its chunks +
vectors. Per-record failures are logged and counted, never fatal. Each run is
recorded in the ingest log.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime

from odr.embed.base import Embedder
from odr.sources.base import Source
from odr.store.base import Store
from odr.types import IngestRun

logger = logging.getLogger(__name__)


def run_ingest(
    source: Source,
    store: Store,
    embedder: Embedder,
    *,
    since: date | None = None,
    limit: int | None = None,
) -> IngestRun:
    store.upsert_source(source.meta)  # record provenance up front
    chunker = source.chunker  # each source declares its chunking strategy
    started = datetime.now(UTC)
    seen = new = updated = errors = 0

    for raw in source.fetch(since=since, limit=limit):
        seen += 1
        try:
            doc = source.normalise(raw)
            if store.content_hash_exists(doc.content_hash):
                continue  # unchanged duplicate — don't re-embed
            existed = store.document_exists(doc.source_id, doc.source_ref)
            doc_id = store.upsert_document(doc)
            chunks = chunker.chunk(doc_id, doc)
            if chunks:
                vectors = embedder.embed([c.text for c in chunks])
                store.upsert_chunks(doc_id, chunks, vectors, embedder.model_id)
            if existed:
                updated += 1
            else:
                new += 1
        except Exception:  # noqa: BLE001 - per-record resilience; one bad record must not abort the run
            errors += 1
            logger.warning("ingest: skipping record %d", seen, exc_info=True)

    run = IngestRun(
        source_id=source.meta.id,
        started_at=started,
        finished_at=datetime.now(UTC),
        status="ok" if errors == 0 else "partial",
        docs_seen=seen,
        docs_new=new,
        docs_updated=updated,
        error=None if errors == 0 else f"{errors} record(s) failed",
    )
    store.record_ingest_run(run)
    return run
