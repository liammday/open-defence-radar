"""FastAPI app: the grounded query console + trust dashboard (design §7).

`create_app` takes an injectable `query_fn` (the answer use-case) and
`context_provider` (the corpus/eval view-model), so the routes can be tested
against fakes without a live model, store, or network. The HTTP `POST /query`
returns the same JSON contract as the MCP `query` tool (design §4).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from odr.eval.runner import load_thresholds
from odr.query import answer_query, answer_to_dict, build_filters
from odr.types import Answer, Filters, SourceStat
from odr.web.trust import TrustView, load_trust_view

QueryFn = Callable[[str, int, Filters | None], Answer]

_log = logging.getLogger("odr.web")


def _error_reason(exc: Exception) -> str:
    """A concise, human-readable reason from a query/generation failure."""
    message = str(exc).strip()
    return (message.splitlines()[0] if message else exc.__class__.__name__)[:200]


_HERE = Path(__file__).resolve().parent
_templates = Jinja2Templates(directory=str(_HERE / "templates"))

_EXAMPLES = (
    "Recent MoD AI procurement awards",
    "Tenders citing autonomy or autonomous systems",
    "Counter-UAS or drone-defence announcements",
)


@dataclass(frozen=True)
class SiteContext:
    """View-model shared by both pages: corpus readout + provenance + trust."""

    source_count: int
    document_count: int
    provenance: tuple[SourceStat, ...]
    trust: TrustView | None


ContextProvider = Callable[[], SiteContext]


def _default_context() -> SiteContext:
    """Live context from the SQLite store + eval artifacts (read fresh per request)."""
    from odr.store.sqlite_store import SqliteStore

    db_path = Path(os.environ.get("ODR_DB_PATH", "data/odr.sqlite3"))
    db_path.parent.mkdir(parents=True, exist_ok=True)  # first run: create the data dir
    store = SqliteStore(db_path)
    store.init_schema()  # no-op on an existing store; creates empty tables otherwise
    provenance = tuple(store.source_breakdown())
    eval_dir = os.environ.get("ODR_EVAL_DIR", "data/eval")
    return SiteContext(
        source_count=len(provenance),
        document_count=store.document_count(),
        provenance=provenance,
        trust=load_trust_view(eval_dir, load_thresholds()),
    )


class QueryRequest(BaseModel):
    """The `POST /query` body — mirrors the MCP tool's arguments."""

    topic: str
    k: int = 8
    date_from: str | None = None
    date_to: str | None = None
    sources: list[str] | None = None


def create_app(
    query_fn: QueryFn = answer_query,
    *,
    context_provider: ContextProvider = _default_context,
) -> FastAPI:
    app = FastAPI(
        title="open-defence-radar",
        description="Grounded retrieval over open defence-and-security signals.",
    )
    app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/query")
    def query(req: QueryRequest) -> JSONResponse:
        filters = build_filters(req.date_from, req.date_to, req.sources)
        try:
            return JSONResponse(content=answer_to_dict(query_fn(req.topic, req.k, filters)))
        except Exception as exc:
            # Boundary: surface a structured error with the real reason instead of a bare
            # 500, and log the full trace server-side — never a silent failure.
            _log.exception("query failed for topic=%r", req.topic)
            return JSONResponse(status_code=502, content={"error": _error_reason(exc)})

    @app.get("/", response_class=HTMLResponse)
    def console(request: Request) -> HTMLResponse:
        return _templates.TemplateResponse(
            request,
            "console.html",
            {"site": context_provider(), "active": "console", "examples": _EXAMPLES},
        )

    @app.get("/trust", response_class=HTMLResponse)
    def trust(request: Request) -> HTMLResponse:
        return _templates.TemplateResponse(
            request,
            "trust.html",
            {"site": context_provider(), "active": "trust"},
        )

    return app


def main() -> None:
    """Console-script entry point: serve the app with uvicorn (local dev)."""
    load_dotenv()  # pick up ODR_* / GOOGLE_API_KEY etc. from a local .env
    host = os.environ.get("ODR_WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("ODR_WEB_PORT", "8000"))
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
