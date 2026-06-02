"""Entailment judge: caching + yes/no parsing (with a fake generator)."""

from __future__ import annotations

from odr.eval.judge import FakeJudge, Judge, LLMJudge
from odr.synthesise.fake_generator import FakeGenerator


def _requires_judge(_j: Judge) -> None: ...


class _CountingGenerator:
    model_id = "counting"

    def __init__(self) -> None:
        self.calls = 0

    def generate(
        self, system: str, user: str, *, max_tokens: int = 1024, temperature: float = 0.0
    ) -> str:
        self.calls += 1
        return "yes"


def test_judges_conform_to_protocol() -> None:
    _requires_judge(FakeJudge())
    _requires_judge(LLMJudge(generator=FakeGenerator("yes")))


def test_fake_judge_uses_rule() -> None:
    judge = FakeJudge(lambda claim, passage: "moon" in passage)
    assert judge.judge("claim", "the moon is bright") is True
    assert judge.judge("claim", "the sun is bright") is False


def test_anthropic_judge_caches_by_pair() -> None:
    gen = _CountingGenerator()
    judge = LLMJudge(generator=gen)
    assert judge.judge("claim", "passage") is True
    assert judge.judge("claim", "passage") is True
    assert gen.calls == 1  # second identical pair served from cache
    judge.judge("claim", "different passage")
    assert gen.calls == 2  # new pair → new call


def test_anthropic_judge_parses_no() -> None:
    judge = LLMJudge(generator=FakeGenerator("No — the passage does not support it."))
    assert judge.judge("claim", "passage") is False
