"""A generator that returns a fixed, scripted response — for tests."""

from __future__ import annotations


class FakeGenerator:
    model_id = "fake-generator"

    def __init__(self, response: str) -> None:
        self._response = response

    def generate(
        self, system: str, user: str, *, max_tokens: int = 1024, temperature: float = 0.0
    ) -> str:
        return self._response
