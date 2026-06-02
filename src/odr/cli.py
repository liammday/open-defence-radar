"""Command-line interface for open-defence-radar.

The `ingest`, `query`, `eval`, and `serve` commands are added in their
respective Phase 0/1 issues; this scaffold establishes the entry point.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import date
from pathlib import Path

import typer
from dotenv import load_dotenv

from odr import __version__
from odr.embed.factory import get_embedder
from odr.eval.judge import LLMJudge
from odr.eval.runner import run_eval, write_result
from odr.ingest.pipeline import run_ingest
from odr.query import answer_query, build_filters
from odr.sources.base import Source
from odr.sources.contracts_finder import ContractsFinder
from odr.sources.find_a_tender import FindATender
from odr.sources.govuk_news import GovUkNews
from odr.store.sqlite_store import SqliteStore
from odr.synthesise.factory import get_generator

app = typer.Typer(
    help="open-defence-radar — grounded RAG over open defence-and-security signals.",
    no_args_is_help=True,
)

# Source registry — one entry per source adapter.
_SOURCES: dict[str, Callable[[], Source]] = {
    "contracts-finder": ContractsFinder,
    "find-a-tender": FindATender,
    "govuk-mod": GovUkNews,
}


@app.callback()
def _root() -> None:
    """open-defence-radar CLI.

    A root callback keeps Typer in multi-command "group" mode so subcommands
    (``version`` now; ``ingest``/``query``/``eval``/``serve`` later) route by name.
    """


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


@app.command()
def ingest(
    source: str = typer.Argument(..., help="Source id, e.g. 'contracts-finder'"),
    limit: int | None = typer.Option(None, help="Max records to ingest"),
    since: str | None = typer.Option(None, help="Only records published on/after YYYY-MM-DD"),
    incremental: bool = typer.Option(
        False, "--incremental", help="Resume from the newest stored date for this source"
    ),
) -> None:
    """Ingest an open source into the local store."""
    if source not in _SOURCES:
        known = ", ".join(sorted(_SOURCES))
        raise typer.BadParameter(f"unknown source {source!r} (known: {known})")
    src = _SOURCES[source]()
    embedder = get_embedder()
    store = SqliteStore(os.environ.get("ODR_DB_PATH", "data/odr.sqlite3"), dim=embedder.dim)
    store.init_schema()
    since_date = date.fromisoformat(since) if since else None
    if incremental and since_date is None:
        since_date = store.latest_published(src.meta.id)
    run = run_ingest(src, store, embedder, since=since_date, limit=limit)
    typer.echo(
        f"{run.source_id}: {run.docs_seen} seen, {run.docs_new} new, "
        f"{run.docs_updated} updated — {run.status}"
    )


@app.command()
def query(
    topic: str = typer.Argument(..., help="What to ask"),
    k: int = typer.Option(8, help="Number of passages to retrieve"),
    date_from: str | None = typer.Option(None, "--date-from", help="Only on/after YYYY-MM-DD"),
    date_to: str | None = typer.Option(None, "--date-to", help="Only on/before YYYY-MM-DD"),
    source: list[str] | None = typer.Option(None, "--source", help="Restrict to source id(s)"),
) -> None:
    """Ask a grounded, cited question over the ingested corpus."""
    answer = answer_query(topic, k=k, filters=build_filters(date_from, date_to, source))

    typer.echo(answer.text)
    if answer.citations:
        typer.echo("\nSources:")
        for c in answer.citations:
            published = c.published_at.isoformat() if c.published_at else None
            bits = " · ".join(p for p in (c.source_name, published, c.document_title) if p)
            typer.echo(f"  {c.marker} {bits} — {c.url}")
    g = answer.groundedness
    typer.echo(
        f"\nGroundedness: {g.supported}/{g.total_claims} claims supported (score {g.score:.2f})"
    )


@app.command()
def agent(
    question: str = typer.Argument(..., help="A broad question to decompose"),
    k: int = typer.Option(8, help="Passages to retrieve per sub-query"),
) -> None:
    """Decompose a broad question across multiple grounded queries into one cited brief."""
    from odr.agent.orchestrator import decompose_and_answer
    from odr.agent.planner import LLMPlanner

    brief = decompose_and_answer(question, planner=LLMPlanner(), k=k)

    typer.echo(f"Sub-questions ({len(brief.sub_questions)}):")
    for sub in brief.sub_questions:
        typer.echo(f"  - {sub}")
    typer.echo("")
    typer.echo(brief.text)
    if brief.citations:
        typer.echo("\nSources:")
        for c in brief.citations:
            published = c.published_at.isoformat() if c.published_at else None
            bits = " · ".join(p for p in (c.source_name, published, c.document_title) if p)
            typer.echo(f"  {c.marker} {bits} — {c.url}")
    g = brief.groundedness
    typer.echo(
        f"\nGroundedness: {g.supported}/{g.total_claims} claims supported (score {g.score:.2f})"
    )


@app.command(name="eval")
def evaluate() -> None:
    """Run the evaluation harness against the fixture corpus; write data/eval/latest.json."""
    result = run_eval(get_embedder(), get_generator(), LLMJudge())
    path = write_result(result, Path(os.environ.get("ODR_EVAL_DIR", "data/eval")))
    typer.echo(
        f"hit-rate {result.hit_rate:.2f} · recall@k {result.recall_at_k:.2f} · "
        f"MRR {result.mrr:.2f} · groundedness {result.groundedness:.2f} · "
        f"unsupported {result.unsupported_claim_rate:.2f} ({result.question_count} questions)"
    )
    typer.echo(f"written: {path}")


def main() -> None:
    """Console-script entry point (see ``[project.scripts]`` in pyproject)."""
    load_dotenv()  # pick up GOOGLE_API_KEY etc. from a local .env
    app()


if __name__ == "__main__":
    main()
