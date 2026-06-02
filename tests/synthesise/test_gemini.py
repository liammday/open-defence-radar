"""Gemini generator — request building + response parsing (offline via MockTransport)."""

from __future__ import annotations

import json

import httpx
import pytest

from odr.synthesise.anthropic_generator import AnthropicGenerator
from odr.synthesise.base import Generator
from odr.synthesise.factory import get_generator
from odr.synthesise.gemini_generator import GeminiGenerator


def _requires_generator(_g: Generator) -> None: ...


def test_factory_defaults_to_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ODR_GENERATOR", raising=False)
    assert isinstance(get_generator(), GeminiGenerator)
    assert isinstance(get_generator("anthropic"), AnthropicGenerator)
    with pytest.raises(ValueError, match="generator"):
        get_generator("nope")


def test_gemini_conforms_to_protocol() -> None:
    _requires_generator(GeminiGenerator(api_key="k"))


def test_generate_builds_request_and_parses_response() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["api_key"] = request.headers.get("x-goog-api-key")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": "Grounded answer [1]."}]}}]}
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    gen = GeminiGenerator(api_key="secret", client=client, model_id="gemini-2.0-flash")
    out = gen.generate("SYSTEM", "USER", max_tokens=64, temperature=0.0)

    assert out == "Grounded answer [1]."
    assert "gemini-2.0-flash:generateContent" in captured["url"]  # type: ignore[operator]
    # the key travels in a header and must NEVER appear in the URL (it would leak
    # into tracebacks/logs otherwise)
    assert captured["api_key"] == "secret"
    assert "secret" not in captured["url"]  # type: ignore[operator]
    body = captured["body"]
    assert body["systemInstruction"]["parts"][0]["text"] == "SYSTEM"  # type: ignore[index]
    assert body["contents"][0]["parts"][0]["text"] == "USER"  # type: ignore[index]


def test_generate_without_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        GeminiGenerator().generate("s", "u")


def test_rate_limit_raises_clean_error_without_leaking_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={"error": {"message": "Quota exceeded for free tier", "status": "EXHAUSTED"}},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    gen = GeminiGenerator(api_key="secret", client=client)
    with pytest.raises(RuntimeError, match="429") as exc:
        gen.generate("s", "u")
    assert "Quota exceeded for free tier" in str(exc.value)  # Google's reason is surfaced
    assert "secret" not in str(exc.value)  # the key must never appear in errors
