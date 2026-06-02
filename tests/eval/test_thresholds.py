"""The eval CI gate: metrics must clear the floors in thresholds.json.

This test runs in CI (it's just pytest). The retrieval floors gate offline (the
hybrid keyword path carries the fixture questions, so no key/model is needed to
guard the retrieval *pipeline*). The groundedness floor gates only when a real
ANTHROPIC_API_KEY is present, since it needs the entailment judge.
"""

from __future__ import annotations

import os

import pytest

from odr.embed.fake import FakeEmbedder
from odr.eval.judge import FakeJudge
from odr.eval.runner import load_thresholds, run_eval
from odr.synthesise.fake_generator import FakeGenerator

_THRESHOLDS = load_thresholds()


def test_retrieval_metrics_clear_floors() -> None:
    result = run_eval(
        FakeEmbedder(dim=384),
        FakeGenerator("The notice is relevant [1]."),
        FakeJudge(lambda claim, passage: True),
    )
    assert result.hit_rate >= _THRESHOLDS["hit_rate"]
    assert result.recall_at_k >= _THRESHOLDS["recall_at_k"]
    assert result.mrr >= _THRESHOLDS["mrr"]


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="groundedness gate needs the real entailment judge (an API key)",
)
def test_groundedness_clears_floor_with_real_providers() -> None:
    from odr.embed.factory import get_embedder
    from odr.eval.judge import LLMJudge
    from odr.synthesise.factory import get_generator

    result = run_eval(get_embedder(), get_generator(), LLMJudge())
    assert result.groundedness >= _THRESHOLDS["groundedness"]
    assert result.unsupported_claim_rate <= _THRESHOLDS["unsupported_claim_rate"]
