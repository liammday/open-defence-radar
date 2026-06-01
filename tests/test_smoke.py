"""Scaffold smoke tests — prove the package imports and the CLI runs."""

from __future__ import annotations

from typer.testing import CliRunner

from odr import __version__
from odr.cli import app

runner = CliRunner()


def test_version_is_set() -> None:
    assert __version__


def test_cli_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_cli_ingest_rejects_unknown_source() -> None:
    # Errors before any network/model work, so this stays offline.
    result = runner.invoke(app, ["ingest", "no-such-source"])
    assert result.exit_code != 0
