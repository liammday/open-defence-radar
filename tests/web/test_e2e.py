"""End-to-end browser smoke (opt-in).

Runs the real app — with a fake query function and context, so no model, store, or
network — under a background uvicorn server, and drives it with Playwright/Chromium.
Asserts the console renders a grounded answer with citation chips and no console
errors, the trust dashboard renders its metrics, and a backend failure surfaces a
structured error (the real reason, not a generic hint).

Skipped unless ODR_E2E=1; needs a browser: `uv run playwright install chromium`.
"""

from __future__ import annotations

import os
import socket
import threading
import time
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date

import pytest
import uvicorn
from fastapi import FastAPI

from odr.types import Answer, Citation, Filters, GroundednessReport, ScoredChunk, SourceStat
from odr.web.app import SiteContext, create_app
from odr.web.trust import MetricView, TrustView

pytestmark = pytest.mark.skipif(
    not os.environ.get("ODR_E2E"),
    reason="e2e smoke is opt-in: set ODR_E2E=1 and run `playwright install chromium`",
)


def _answer() -> Answer:
    return Answer(
        text="The MoD funded autonomous systems [1] and AI tooling [2].",
        citations=(
            Citation(
                "[1]",
                "c1",
                "Autonomy contract",
                "Find a Tender",
                "https://www.find-tender.service.gov.uk/n/1",
                date(2026, 1, 1),
            ),
            Citation(
                "[2]",
                "c2",
                "AI tooling award",
                "UK Contracts Finder",
                "https://www.contractsfinder.service.gov.uk/n/2",
                date(2026, 2, 1),
            ),
        ),
        groundedness=GroundednessReport(total_claims=2, supported=2, unsupported=0),
        retrieved=(
            ScoredChunk("c1", "d1", "Autonomy contract", "…", 0.9, "Find a Tender", "https://x/1"),
            ScoredChunk(
                "c2", "d2", "AI tooling award", "…", 0.8, "Contracts Finder", "https://x/2"
            ),
        ),
    )


def _ctx() -> SiteContext:
    metric = MetricView(
        "groundedness",
        "Groundedness",
        0.95,
        0.9,
        False,
        True,
        "good",
        "entailment-judged",
        "How often claims are supported by a passage.",
        (0.95,),
    )
    prov = (
        SourceStat("contracts-finder", "UK Contracts Finder", "OGL v3.0", "OCDS API", 42, None),
    )
    return SiteContext(
        source_count=1,
        document_count=42,
        provenance=prov,
        trust=TrustView("2026-06-02T09:51:42+00:00", 10, (metric,)),
    )


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = int(s.getsockname()[1])
    s.close()
    return port


@contextmanager
def _serve(app: FastAPI) -> Iterator[str]:
    """Run `app` under a background uvicorn server; yield its base URL."""
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):  # wait for liveness
        try:
            urllib.request.urlopen(url + "/healthz", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    try:
        yield url
    finally:
        server.should_exit = True
        thread.join(timeout=5)


@pytest.fixture(scope="module")
def server_url() -> Iterator[str]:
    app = create_app(query_fn=lambda topic, k, filters: _answer(), context_provider=_ctx)
    with _serve(app) as url:
        yield url


@pytest.fixture(scope="module")
def error_server_url() -> Iterator[str]:
    def boom(topic: str, k: int, filters: Filters | None) -> Answer:
        raise RuntimeError("Gemini API rate-limited (HTTP 429): quota exceeded")

    with _serve(create_app(query_fn=boom, context_provider=_ctx)) as url:
        yield url


def test_console_renders_grounded_answer(server_url: str, page) -> None:  # type: ignore[no-untyped-def]
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))

    page.goto(server_url + "/")
    page.fill("#q", "autonomy contracts")
    page.click("#submit-btn")
    page.wait_for_selector(".cite")

    assert page.locator(".cite").count() == 2  # two citation chips rendered
    assert "1.00" in page.locator("#g-val").inner_text()  # groundedness gauge populated
    assert errors == []


def test_trust_renders_metrics(server_url: str, page) -> None:  # type: ignore[no-untyped-def]
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    page.goto(server_url + "/trust")
    page.wait_for_selector(".meter")

    assert page.locator(".meter .explain").count() >= 1  # plain-English captions present
    assert "all floors met" in page.content()
    assert errors == []


def test_console_surfaces_the_real_error(error_server_url: str, page) -> None:  # type: ignore[no-untyped-def]
    page.goto(error_server_url + "/")
    page.fill("#q", "anything")
    page.click("#submit-btn")
    page.wait_for_selector("#status-msg:not([hidden])")

    msg = page.locator("#status-msg").inner_text()
    assert "rate-limited" in msg  # the real backend reason is shown
    assert "Is the model server" not in msg  # not the old generic LM-Studio hint
