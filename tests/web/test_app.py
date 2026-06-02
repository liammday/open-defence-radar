"""Web app: the FastAPI routes (design §7 slice 1).

The app factory takes an injectable `query_fn`, so the routes are exercised
against a fake answer — no live model, store, or network.
"""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from odr.query import answer_to_dict
from odr.types import Answer, Citation, Filters, GroundednessReport, ScoredChunk
from odr.web.app import create_app


def _sample_answer() -> Answer:
    return Answer(
        text="The MoD bought AI tooling [1].",
        citations=(
            Citation(
                marker="[1]",
                chunk_id="c1",
                document_title="Doc One",
                source_name="Contracts Finder",
                url="https://example.gov.uk/c1",
                published_at=date(2026, 1, 1),
            ),
        ),
        groundedness=GroundednessReport(total_claims=1, supported=1, unsupported=0),
        retrieved=(
            ScoredChunk(
                chunk_id="c1",
                document_id="d1",
                title="Doc One",
                text="AI tooling",
                score=0.9,
                source_name="Contracts Finder",
                url="https://example.gov.uk/c1",
            ),
        ),
    )


def test_query_returns_cited_answer_contract() -> None:
    answer = _sample_answer()

    def fake(topic: str, k: int, filters: Filters | None) -> Answer:
        return answer

    client = TestClient(create_app(query_fn=fake))
    resp = client.post("/query", json={"topic": "AI contracts"})

    assert resp.status_code == 200
    assert resp.json() == answer_to_dict(answer)


def test_query_passes_parsed_filters_to_use_case() -> None:
    captured: dict[str, object] = {}

    def fake(topic: str, k: int, filters: Filters | None) -> Answer:
        captured["topic"] = topic
        captured["k"] = k
        captured["filters"] = filters
        return _sample_answer()

    client = TestClient(create_app(query_fn=fake))
    resp = client.post(
        "/query",
        json={
            "topic": "drones",
            "k": 5,
            "date_from": "2026-01-01",
            "sources": ["contracts-finder"],
        },
    )

    assert resp.status_code == 200
    assert captured["topic"] == "drones"
    assert captured["k"] == 5
    filters = captured["filters"]
    assert isinstance(filters, Filters)
    assert filters.date_from == date(2026, 1, 1)
    assert filters.date_to is None
    assert filters.sources == ("contracts-finder",)


def test_healthz_returns_ok() -> None:
    client = TestClient(create_app())
    resp = client.get("/healthz")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_console_page_renders_html() -> None:
    client = TestClient(create_app())
    resp = client.get("/")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    # Identity + the non-negotiable open-sources guardrail banner (design §2).
    assert "open-defence-radar" in resp.text
    assert "OPEN SOURCES ONLY" in resp.text
    assert "Console" in resp.text


def test_trust_page_renders_html() -> None:
    client = TestClient(create_app())
    resp = client.get("/trust")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "open-defence-radar" in resp.text
    assert "Trust" in resp.text
