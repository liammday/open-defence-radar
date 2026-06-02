"""Web app: the FastAPI routes (design §7).

The app factory takes an injectable `query_fn` and `context_provider`, so the
routes are exercised against fakes — no live model, store, or network.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from odr.query import answer_to_dict
from odr.types import (
    Answer,
    Citation,
    Filters,
    GroundednessReport,
    ScoredChunk,
    SourceStat,
)
from odr.web.app import SiteContext, create_app
from odr.web.trust import MetricView, TrustView


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


def _ctx(trust: TrustView | None = None, provenance: tuple[SourceStat, ...] = ()) -> SiteContext:
    return SiteContext(
        source_count=len(provenance),
        document_count=sum(s.document_count for s in provenance),
        provenance=provenance,
        trust=trust,
    )


def _sample_trust(passed: bool = True) -> TrustView:
    metric = MetricView(
        key="groundedness",
        label="Groundedness",
        value=0.95,
        bound=0.9,
        inverted=False,
        passed=passed,
        fill_class="good",
        detail="entailment-judged",
        explanation="How often the answer's claims are supported by a retrieved passage.",
        history=(0.95,),
    )
    return TrustView(generated_at="2026-06-02T09:51:42+00:00", question_count=10, metrics=(metric,))


# ── POST /query (the data endpoint) ─────────────────────────────────────────


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


# ── GET / (console page) ─────────────────────────────────────────────────────


def test_console_page_renders_query_form_and_guardrail() -> None:
    client = TestClient(create_app(context_provider=_ctx))
    resp = client.get("/")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert 'id="query-form"' in resp.text
    assert "Ask the open signals" in resp.text
    assert "open sources only" in resp.text  # the guardrail banner (CSS uppercases it)
    assert 'class="inputbox"' in resp.text  # the bordered, obviously-editable input
    assert "pick an example" in resp.text  # the affordance hint
    assert 'id="loading"' in resp.text  # the in-flight progress block
    # fonts are self-hosted: no runtime Google Fonts dependency
    assert "/static/fonts.css" in resp.text
    assert "fonts.googleapis.com" not in resp.text
    # a11y: a <main> landmark, aria-current on the active nav link, live regions
    assert "<main" in resp.text
    assert 'aria-current="page"' in resp.text
    assert 'role="status"' in resp.text


def test_console_shows_corpus_readout() -> None:
    prov = (
        SourceStat("contracts-finder", "UK Contracts Finder", "OGL v3.0", "OCDS API", 137, None),
    )
    client = TestClient(create_app(context_provider=lambda: _ctx(provenance=prov)))
    resp = client.get("/")

    assert "137" in resp.text  # document count surfaced in the status bar
    assert "documents" in resp.text


# ── GET /trust (dashboard page) ──────────────────────────────────────────────


def test_trust_page_renders_metrics_and_provenance() -> None:
    prov = (
        SourceStat(
            "contracts-finder",
            "UK Contracts Finder",
            "OGL v3.0",
            "OCDS API",
            42,
            datetime(2026, 5, 30, 4, 12),
        ),
    )
    client = TestClient(
        create_app(context_provider=lambda: _ctx(trust=_sample_trust(), provenance=prov))
    )
    resp = client.get("/trust")

    assert resp.status_code == 200
    assert "Groundedness" in resp.text
    assert "0.95" in resp.text
    assert "all floors met" in resp.text
    assert "supported by a retrieved passage" in resp.text  # plain-English caption
    assert "UK Contracts Finder" in resp.text
    assert "OCDS API" in resp.text


def test_trust_page_flags_breach() -> None:
    client = TestClient(
        create_app(context_provider=lambda: _ctx(trust=_sample_trust(passed=False)))
    )
    resp = client.get("/trust")

    assert resp.status_code == 200
    assert "all floors met" not in resp.text


def test_trust_page_no_eval_is_graceful() -> None:
    client = TestClient(create_app(context_provider=_ctx))
    resp = client.get("/trust")

    assert resp.status_code == 200
    assert "No evaluation has been run" in resp.text


def test_default_context_creates_missing_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # First run / container: ODR_DB_PATH points into a not-yet-created dir.
    from odr.web.app import _default_context

    db = tmp_path / "fresh" / "odr.sqlite3"
    monkeypatch.setenv("ODR_DB_PATH", str(db))
    monkeypatch.setenv("ODR_EVAL_DIR", str(tmp_path / "eval"))

    ctx = _default_context()  # must not raise apsw.CantOpenError

    assert db.parent.is_dir()
    assert ctx.document_count == 0
    assert ctx.trust is None
