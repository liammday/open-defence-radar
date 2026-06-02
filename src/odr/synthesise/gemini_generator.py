"""Google Gemini generator (free-tier via Google AI Studio).

Uses the Generative Language REST API directly over httpx (no extra dependency).
A free API key (no card) comes from https://aistudio.google.com/apikey; set it as
GOOGLE_API_KEY. Model via ODR_GEMINI_MODEL (default gemini-2.0-flash).
"""

from __future__ import annotations

import os
from typing import Any

import httpx

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiGenerator:
    def __init__(
        self,
        model_id: str | None = None,
        api_key: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.model_id = model_id or os.environ.get("ODR_GEMINI_MODEL", "gemini-2.0-flash")
        self._api_key = (
            api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        )
        self._client = client or httpx.Client(timeout=60.0)

    def generate(
        self, system: str, user: str, *, max_tokens: int = 1024, temperature: float = 0.0
    ) -> str:
        if not self._api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set")
        resp = self._client.post(
            f"{_BASE}/{self.model_id}:generateContent",
            params={"key": self._api_key},
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"parts": [{"text": user}]}],
                "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
            },
        )
        resp.raise_for_status()
        data: Any = resp.json()
        parts = data["candidates"][0]["content"].get("parts", [])
        return "".join(part.get("text", "") for part in parts)
