"""Eval runner: runs the fixture question set -> metrics -> JSON artifact (offline)."""

from __future__ import annotations

import json

from odr.embed.fake import FakeEmbedder
from odr.eval.judge import FakeJudge
from odr.eval.runner import run_eval, write_result
from odr.synthesise.fake_generator import FakeGenerator


def test_run_eval_produces_all_metrics() -> None:
    result = run_eval(
        FakeEmbedder(dim=8),
        FakeGenerator("The notice is relevant [1]."),
        FakeJudge(lambda claim, passage: True),
    )
    assert result.question_count == 10
    for value in (result.hit_rate, result.recall_at_k, result.mrr, result.groundedness):
        assert 0.0 <= value <= 1.0
    assert result.unsupported_claim_rate == round(1.0 - result.groundedness, 6)


def test_write_result_emits_latest_json(tmp_path) -> None:  # type: ignore[no-untyped-def]
    result = run_eval(
        FakeEmbedder(dim=8), FakeGenerator("relevant [1]."), FakeJudge(lambda c, p: True)
    )
    path = write_result(result, tmp_path)
    assert path == tmp_path / "latest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["question_count"] == 10
    assert {"hit_rate", "recall_at_k", "mrr", "groundedness", "unsupported_claim_rate"} <= set(data)
