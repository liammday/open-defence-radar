"""Command-line interface for open-defence-radar.

The `ingest`, `query`, `eval`, and `serve` commands are added in their
respective Phase 0/1 issues; this scaffold establishes the entry point.
"""

from __future__ import annotations

import typer

from odr import __version__

app = typer.Typer(
    help="open-defence-radar — grounded RAG over open defence-and-security signals.",
    no_args_is_help=True,
)


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


def main() -> None:
    """Console-script entry point (see ``[project.scripts]`` in pyproject)."""
    app()


if __name__ == "__main__":
    main()
