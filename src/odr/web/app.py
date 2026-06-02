"""FastAPI app: the grounded query console + trust dashboard (design §7).

The app is built by `create_app`, which takes an injectable `query_fn` (defaults
to the shared `answer_query` use-case) so the routes can be tested against a fake
answer without a live model, store, or network. The HTTP `POST /query` returns the
same JSON contract as the MCP `query` tool (design §4 — no new backend shapes).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from odr.query import answer_query, answer_to_dict, build_filters
from odr.types import Answer, Filters

QueryFn = Callable[[str, int, Filters | None], Answer]


def _placeholder_page(active: str, lede: str) -> str:
    """A minimal page shell carrying the wordmark + open-sources guardrail banner.

    Slice 1 stands the routes up; the prototype UI (Jinja templates) is ported in
    the next slice (epic #5), which replaces this shell.
    """
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>open-defence-radar — {active}</title>
</head>
<body>
  <header>
    <span class="wordmark">open-defence-radar</span>
    <span class="guardrail">OPEN SOURCES ONLY</span>
    <nav><a href="/">Console</a> · <a href="/trust">Trust</a></nav>
  </header>
  <main>
    <h1>{active}</h1>
    <p>{lede}</p>
    <p>Placeholder — the prototype UI lands when the Jinja templates are ported.</p>
  </main>
</body>
</html>"""


class QueryRequest(BaseModel):
    """The `POST /query` body — mirrors the MCP tool's arguments."""

    topic: str
    k: int = 8
    date_from: str | None = None
    date_to: str | None = None
    sources: list[str] | None = None


def create_app(query_fn: QueryFn = answer_query) -> FastAPI:
    app = FastAPI(
        title="open-defence-radar",
        description="Grounded retrieval over open defence-and-security signals.",
    )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/query")
    def query(req: QueryRequest) -> dict[str, Any]:
        filters = build_filters(req.date_from, req.date_to, req.sources)
        return answer_to_dict(query_fn(req.topic, req.k, filters))

    @app.get("/", response_class=HTMLResponse)
    def console() -> str:
        return _placeholder_page(
            "Console", "Ask a question; every claim is traced to a cited open source."
        )

    @app.get("/trust", response_class=HTMLResponse)
    def trust() -> str:
        return _placeholder_page("Trust", "Evaluation metrics and source provenance.")

    return app


def main() -> None:
    """Console-script entry point: serve the app with uvicorn (local dev)."""
    load_dotenv()  # pick up ODR_* / GOOGLE_API_KEY etc. from a local .env
    host = os.environ.get("ODR_WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("ODR_WEB_PORT", "8000"))
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
