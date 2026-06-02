"""Generator selection — `ODR_GENERATOR` (default: gemini, the free-tier option)."""

from __future__ import annotations

import os

from odr.synthesise.anthropic_generator import AnthropicGenerator
from odr.synthesise.base import Generator
from odr.synthesise.gemini_generator import GeminiGenerator
from odr.synthesise.openai_compatible import OpenAICompatibleGenerator


def get_generator(name: str | None = None) -> Generator:
    name = (name or os.environ.get("ODR_GENERATOR") or "gemini").lower()
    if name == "gemini":
        return GeminiGenerator()
    if name == "anthropic":
        return AnthropicGenerator()
    if name == "lmstudio":  # any OpenAI-compatible local server (LM Studio, Ollama, vLLM)
        return OpenAICompatibleGenerator()
    raise ValueError(f"Unknown generator {name!r} (expected 'gemini', 'anthropic', or 'lmstudio')")
