"""Claude-backed generator (the default for synthesis).

Reads ANTHROPIC_API_KEY from the environment; the model is overridable via
ODR_ANTHROPIC_MODEL. The SDK + client load lazily, so constructing this without
a key is fine (generate() is where a missing key raises).
"""

from __future__ import annotations

import os
from typing import Any

_DEFAULT_MODEL = "claude-sonnet-4-6"


class AnthropicGenerator:
    def __init__(self, model_id: str | None = None, api_key: str | None = None) -> None:
        self.model_id = model_id or os.environ.get("ODR_ANTHROPIC_MODEL", _DEFAULT_MODEL)
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client: Any | None = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            if not self._api_key:
                raise RuntimeError("ANTHROPIC_API_KEY is not set")
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def generate(
        self, system: str, user: str, *, max_tokens: int = 1024, temperature: float = 0.0
    ) -> str:
        message = self._ensure_client().messages.create(
            model=self.model_id,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(getattr(block, "text", "") for block in message.content)
