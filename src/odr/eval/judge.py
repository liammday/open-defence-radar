"""Entailment judge — does a cited passage actually support a claim?

This is the eval-time groundedness check (stronger than the synthesis-time
marker check). The Anthropic judge caches by (claim, passage) so re-running the
eval doesn't re-pay for unchanged pairs.
"""

from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
from typing import Protocol

from odr.synthesise.base import Generator
from odr.synthesise.factory import get_generator


class Judge(Protocol):
    def judge(self, claim: str, passage: str) -> bool: ...


def _always_true(claim: str, passage: str) -> bool:
    return True


class FakeJudge:
    """Deterministic judge for tests — verdict from an injected rule."""

    def __init__(self, fn: Callable[[str, str], bool] | None = None) -> None:
        self._fn = fn or _always_true

    def judge(self, claim: str, passage: str) -> bool:
        return self._fn(claim, passage)


_SYSTEM = (
    "You are a strict fact-checker. Decide whether the PASSAGE supports the CLAIM. "
    "Answer with exactly 'yes' or 'no'."
)


class LLMJudge:
    def __init__(self, generator: Generator | None = None) -> None:
        self._generator = generator or get_generator()
        self._cache: dict[str, bool] = {}

    def judge(self, claim: str, passage: str) -> bool:
        key = sha256(f"{claim}\x00{passage}".encode()).hexdigest()
        if key not in self._cache:
            out = self._generator.generate(
                _SYSTEM,
                f"CLAIM: {claim}\nPASSAGE: {passage}\nDoes the passage support the claim?",
                max_tokens=5,
                temperature=0.0,
            )
            self._cache[key] = out.strip().lower().startswith("y")
        return self._cache[key]
