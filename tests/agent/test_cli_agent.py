"""`odr agent` CLI smoke — formats a Brief; orchestration is mocked (no model)."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from odr.cli import app
from odr.types import Brief, Citation, GroundednessReport


def test_agent_cli_prints_brief(monkeypatch: pytest.MonkeyPatch) -> None:
    brief = Brief(
        question="Q",
        sub_questions=("sub one", "sub two"),
        text="## sub one\nFinding [1].",
        citations=(Citation("[1]", "ch", "A title", "Contracts Finder", "https://u/1", None),),
        groundedness=GroundednessReport(total_claims=2, supported=2, unsupported=0),
    )
    monkeypatch.setattr("odr.agent.planner.LLMPlanner", lambda *a, **k: object())
    monkeypatch.setattr("odr.agent.orchestrator.decompose_and_answer", lambda *a, **k: brief)

    result = CliRunner().invoke(app, ["agent", "Q"])

    assert result.exit_code == 0
    assert "sub one" in result.output and "sub two" in result.output
    assert "[1]" in result.output and "https://u/1" in result.output
    assert "2/2 claims supported" in result.output
