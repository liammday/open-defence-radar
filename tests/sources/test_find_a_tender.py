"""Find a Tender adapter — config over the shared OcdsSource (fetch/normalise
behaviour is covered by the Contracts Finder tests)."""

from __future__ import annotations

import httpx

from odr.sources.base import Source
from odr.sources.find_a_tender import FindATender

SAMPLE = {
    "ocid": "ocds-h6vhtk-06a26f",
    "date": "2026-01-28T09:00:00+00:00",
    "tender": {"title": "Autonomous maritime systems integration"},
    "buyer": {"name": "Ministry of Defence"},
}


def _requires_source(_s: Source) -> None: ...


def test_find_a_tender_conforms_and_meta() -> None:
    src = FindATender()
    _requires_source(src)
    assert src.meta.id == "find-a-tender"
    assert src.meta.licence == "OGL v3.0"


def test_normalise_uses_fts_identity_and_notice_url() -> None:
    doc = FindATender().normalise(SAMPLE)
    assert doc.source_id == "find-a-tender"
    assert doc.source_ref == "ocds-h6vhtk-06a26f"
    assert doc.url == "https://www.find-tender.service.gov.uk/Notice/06a26f"
    assert "Autonomous maritime systems integration" in doc.title
    assert "Ministry of Defence" in doc.text


def test_fetch_hits_fts_endpoint_and_respects_limit() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        return httpx.Response(200, json={"releases": [SAMPLE, SAMPLE, SAMPLE]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    got = list(FindATender(client=client).fetch(limit=2))
    assert len(got) == 2
    assert seen == ["www.find-tender.service.gov.uk"]
