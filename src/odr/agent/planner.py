"""Planning: turn a broad question into focused sub-questions.

`LLMPlanner` uses the configured generator; `FakePlanner` returns a fixed list for
tests (mirrors FakeGenerator / FakeJudge). The planner returns sub-question *strings*
only — the orchestrator owns any filtering and the fallback.
"""

from __future__ import annotations

from typing import Protocol

from odr.synthesise.base import Generator
from odr.synthesise.factory import get_generator

_SYSTEM = (
    "You are a research planner. Break the user's question into 2 to 4 focused, "
    "self-contained sub-questions that together cover it. Output ONE sub-question per "
    "line — no numbering, no bullets, no preamble."
)


class Planner(Protocol):
    def plan(self, question: str) -> list[str]: ...


class FakePlanner:
    """Deterministic planner for tests."""

    def __init__(self, sub_questions: list[str]) -> None:
        self._subs = list(sub_questions)

    def plan(self, question: str) -> list[str]:
        return list(self._subs)


class LLMPlanner:
    def __init__(self, generator: Generator | None = None, max_subs: int = 4) -> None:
        self._generator = generator or get_generator()
        self._max = max_subs

    def plan(self, question: str) -> list[str]:
        # Generous budget: reasoning models (e.g. Gemma 3n) spend hundreds of tokens
        # "thinking" before the sub-questions appear in `content`; too small a cap
        # leaves content empty and forces the orchestrator's fallback.
        out = self._generator.generate(_SYSTEM, question, max_tokens=1024, temperature=0.0)
        subs: list[str] = []
        for line in out.splitlines():
            cleaned = line.lstrip("0123456789.)-*• \t").strip()
            if cleaned and cleaned != question.strip():
                subs.append(cleaned)
        return subs[: self._max]
