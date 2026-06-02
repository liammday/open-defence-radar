"""OpenAI-compatible local generator (LM Studio / Ollama / vLLM) — offline tests."""

from __future__ import annotations

import json

import httpx
import pytest

from odr.synthesise.base import Generator
from odr.synthesise.openai_compatible import OpenAICompatibleGenerator


def _requires_generator(_g: Generator) -> None: ...


def test_conforms_to_protocol() -> None:
    _requires_generator(OpenAICompatibleGenerator(model_id="m", base_url="http://x/v1"))


def test_generate_builds_chat_request_and_parses_response() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "Answer [1]."}}]}
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    gen = OpenAICompatibleGenerator(
        model_id="google/gemma-4-e4b", base_url="http://localhost:1234/v1", client=client
    )
    out = gen.generate("SYSTEM", "USER", max_tokens=64, temperature=0.0)

    assert out == "Answer [1]."
    assert captured["url"] == "http://localhost:1234/v1/chat/completions"
    body = captured["body"]
    assert body["model"] == "google/gemma-4-e4b"  # type: ignore[index]
    assert body["messages"] == [  # type: ignore[index]
        {"role": "system", "content": "SYSTEM"},
        {"role": "user", "content": "USER"},
    ]


def test_empty_api_key_falls_back_to_dummy_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")  # empty, e.g. from a template .env
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    OpenAICompatibleGenerator(base_url="http://x/v1", client=client).generate("s", "u")
    assert captured["auth"] == "Bearer local"  # never an illegal "Bearer "


def test_unreachable_server_raises_friendly_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    gen = OpenAICompatibleGenerator(base_url="http://localhost:1234/v1", client=client)
    with pytest.raises(RuntimeError, match="local LLM server"):
        gen.generate("s", "u")
