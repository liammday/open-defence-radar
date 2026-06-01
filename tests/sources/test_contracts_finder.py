"""Tests for the UK Contracts Finder source adapter.

`normalise` is pure (tested against a representative OCDS release). `fetch` is
tested against an httpx MockTransport — no live network in the suite. Live
reachability + the OGL licence were verified by a spike against the real API
(see PR #28-range notes).
"""

from __future__ import annotations

from datetime import date

import httpx

from odr.sources.base import Source
from odr.sources.contracts_finder import ContractsFinder

SAMPLE_RELEASE = {
    "ocid": "ocds-b5fd17-abc-00000000-0000-0000-0000-000000000001",
    "id": "rel-1",
    "date": "2026-03-14T10:00:00+00:00",
    "tag": ["award"],
    "tender": {
        "title": "AI-assisted intelligence analysis platform",
        "description": "Machine-learning tooling for open-source analysis.",
        "value": {"amount": 250000, "currency": "GBP"},
    },
    "buyer": {"name": "Ministry of Defence"},
    "awards": [{"suppliers": [{"name": "Acme Analytics Ltd"}]}],
}


def _requires_source(_s: Source) -> None:
    """No-op whose signature makes mypy enforce Source conformance."""


def test_contracts_finder_conforms_to_source_protocol() -> None:
    _requires_source(ContractsFinder())


def test_normalise_maps_ocds_release_to_document() -> None:
    doc = ContractsFinder().normalise(SAMPLE_RELEASE)
    assert doc.source_id == "contracts-finder"
    assert doc.source_ref == "ocds-b5fd17-abc-00000000-0000-0000-0000-000000000001"
    assert "AI-assisted intelligence analysis platform" in doc.title
    assert doc.published_at == date(2026, 3, 14)
    assert "Ministry of Defence" in doc.text
    assert "Acme Analytics Ltd" in doc.text
    assert "open-source analysis" in doc.text
    assert doc.content_hash
    assert doc.raw == SAMPLE_RELEASE


def test_normalise_hash_is_deterministic() -> None:
    cf = ContractsFinder()
    assert cf.normalise(SAMPLE_RELEASE).content_hash == cf.normalise(SAMPLE_RELEASE).content_hash


def test_meta_records_ogl_licence_and_access() -> None:
    meta = ContractsFinder().meta
    assert meta.id == "contracts-finder"
    assert meta.licence == "OGL v3.0"
    assert meta.access_method  # e.g. "OCDS API"


def test_fetch_paginates_and_respects_limit() -> None:
    def release(ref: str) -> dict:
        return {**SAMPLE_RELEASE, "ocid": ref}

    def handler(request: httpx.Request) -> httpx.Response:
        if "cursor" in request.url.params:
            return httpx.Response(200, json={"releases": [release("p2-a"), release("p2-b")]})
        next_url = str(request.url.copy_merge_params({"cursor": "PAGE2"}))
        return httpx.Response(
            200,
            json={"releases": [release("p1-a"), release("p1-b")], "links": {"next": next_url}},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    got = list(ContractsFinder(client=client).fetch(limit=3))
    assert len(got) == 3
    assert [r["ocid"] for r in got] == ["p1-a", "p1-b", "p2-a"]
