"""Generator for any OpenAI-compatible local server — LM Studio, Ollama, vLLM.

Free + offline: point it at a local server's /v1 endpoint. Defaults to LM Studio
(http://localhost:1234/v1). Set ODR_LLM_MODEL to the loaded model id (e.g.
"google/gemma-4-e4b"). No real API key is needed (a dummy bearer is sent).
"""

from __future__ import annotations

import os
from typing import Any

import httpx


class OpenAICompatibleGenerator:
    def __init__(
        self,
        model_id: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.model_id = model_id or os.environ.get("ODR_LLM_MODEL", "local-model")
        self._base_url = (
            base_url or os.environ.get("ODR_LLM_BASE_URL", "http://localhost:1234/v1")
        ).rstrip("/")
        # local servers ignore the key; fall back to a non-empty dummy so an empty
        # OPENAI_API_KEY (e.g. from a template .env) doesn't produce an illegal "Bearer " header
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY") or "local"
        self._client = client or httpx.Client(timeout=120.0)  # local models can be slow

    def generate(
        self, system: str, user: str, *, max_tokens: int = 1024, temperature: float = 0.0
    ) -> str:
        try:
            resp = self._client.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self.model_id,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Could not reach a local LLM server at {self._base_url} — is LM Studio's "
                "server started (Developer ▸ Start Server), or Ollama running?"
            ) from exc
        resp.raise_for_status()
        data: Any = resp.json()
        return data["choices"][0]["message"]["content"] or ""
