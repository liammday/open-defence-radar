"""GOV.UK / MoD news source — prose via the GOV.UK Search API; windowed chunking."""

from __future__ import annotations

from datetime import date

import httpx

from odr.ingest.chunk import WindowChunker
from odr.sources.base import Source
from odr.sources.govuk_news import GovUkNews

SAMPLE = {
    "title": "Defence AI strategy progress update",
    "link": "/government/news/defence-ai-strategy-progress",
    "public_timestamp": "2026-02-09T11:00:00Z",
    "description": "An update on defence AI adoption.",
    "indexable_content": "The Ministry of Defence continues to invest in autonomy and data exploitation.",
}


def _requires_source(_s: Source) -> None: ...


def test_govuk_conforms_meta_and_uses_window_chunker() -> None:
    src = GovUkNews()
    _requires_source(src)
    assert src.meta.id == "govuk-mod"
    assert src.meta.licence == "OGL v3.0"
    assert isinstance(src.chunker, WindowChunker)


def test_normalise_maps_search_result_to_document() -> None:
    doc = GovUkNews().normalise(SAMPLE)
    assert doc.source_id == "govuk-mod"
    assert doc.source_ref == "/government/news/defence-ai-strategy-progress"
    assert doc.url == "https://www.gov.uk/government/news/defence-ai-strategy-progress"
    assert doc.published_at == date(2026, 2, 9)
    assert "Defence AI strategy progress update" in doc.text
    assert "autonomy and data exploitation" in doc.text


def test_fetch_respects_limit_and_stops_at_total() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        start = int(request.url.params.get("start", "0"))
        if start == 0:
            return httpx.Response(200, json={"results": [SAMPLE, SAMPLE], "total": 2})
        return httpx.Response(200, json={"results": [], "total": 2})

    all_hits = list(GovUkNews(client=httpx.Client(transport=httpx.MockTransport(handler))).fetch())
    assert len(all_hits) == 2
    limited = list(
        GovUkNews(client=httpx.Client(transport=httpx.MockTransport(handler))).fetch(limit=1)
    )
    assert len(limited) == 1


def test_fetch_since_stops_at_older_results() -> None:
    newer = {**SAMPLE, "public_timestamp": "2026-05-01T00:00:00Z"}
    older = {**SAMPLE, "public_timestamp": "2024-01-01T00:00:00Z"}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [newer, older], "total": 2})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    got = list(GovUkNews(client=client).fetch(since=date(2026, 1, 1)))
    assert len(got) == 1  # newest-first; iteration stops at the first older record
