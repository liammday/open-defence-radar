"""Generator selection — `ODR_GENERATOR` (default: anthropic)."""

from __future__ import annotations

import os

from odr.synthesise.anthropic_generator import AnthropicGenerator
from odr.synthesise.base import Generator


def get_generator(name: str | None = None) -> Generator:
    name = (name or os.environ.get("ODR_GENERATOR") or "anthropic").lower()
    if name == "anthropic":
        return AnthropicGenerator()
    raise ValueError(f"Unknown generator {name!r} (expected 'anthropic')")
