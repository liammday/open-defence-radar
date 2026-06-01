"""The Generator contract — a swappable text-generation provider.

AnthropicGenerator (default, Claude) and FakeGenerator (tests) implement it.
"""

from __future__ import annotations

from typing import Protocol


class Generator(Protocol):
    model_id: str

    def generate(
        self, system: str, user: str, *, max_tokens: int = 1024, temperature: float = 0.0
    ) -> str: ...
