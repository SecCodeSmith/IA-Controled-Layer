from __future__ import annotations

import json

import httpx
import pytest

from control_layer.domain.exceptions import UpstreamProviderError
from control_layer.domain.models.chat import ChatCompletionRequest, ChatMessage
from control_layer.domain.models.provider import ProviderInfo
from control_layer.infrastructure.providers.openai_compatible_provider import (
    OpenAICompatibleModelProvider,
)

BASE_URL = "http://localhost:11434/v1"


def _make_provider(handler, **kwargs) -> OpenAICompatibleModelProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return OpenAICompatibleModelProvider(
        base_url=BASE_URL,
        model="qwen2.5:7b",
        client=client,
        **kwargs,
    )


def _ok_response(payload: dict) -> httpx.Response:
    return httpx.Response(200, json=payload)


CHAT_RESPONSE_PAYLOAD = {
    "id": "chatcmpl-1",
    "object": "chat.completion",
    "created": 1700000000,
    "model": "qwen2.5:7b",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "hello"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
}


def _request(**overrides) -> ChatCompletionRequest:
    base = {"model": "qwen2.5:7b", "messages": [ChatMessage(role="user", content="hi")]}
    base.update(overrides)
    return ChatCompletionRequest(**base)


async def test_describe_returns_provider_info() -> None:
    provider = _make_provider(lambda request: _ok_response(CHAT_RESPONSE_PAYLOAD))
    info = provider.describe()

    assert info == ProviderInfo(name="openai_compatible", model="qwen2.5:7b")


async def test_request_body_shape_with_tools_passthrough() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = json.loads(request.content)
        return _ok_response(CHAT_RESPONSE_PAYLOAD)

    provider = _make_provider(handler)

    tools = [{"type": "function", "function": {"name": "get_run", "parameters": {}}}]
    request = _request(
        tools=tools,
        tool_choice="auto",
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=256,
    )

    await provider.complete(request)

    assert captured["url"] == f"{BASE_URL}/chat/completions"
    sent = captured["json"]
    assert sent["model"] == "qwen2.5:7b"
    assert sent["messages"] == [{"role": "user", "content": "hi"}]
    assert sent["tools"] == tools
    assert sent["tool_choice"] == "auto"
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["temperature"] == 0
    assert sent["max_tokens"] == 256


async def test_omits_optional_fields_when_absent() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content)
        return _ok_response(CHAT_RESPONSE_PAYLOAD)

    provider = _make_provider(handler)
    await provider.complete(_request())

    sent = captured["json"]
    assert "tools" not in sent
    assert "tool_choice" not in sent
    assert "response_format" not in sent


async def test_keep_alive_included_when_configured() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content)
        return _ok_response(CHAT_RESPONSE_PAYLOAD)

    provider = _make_provider(handler, keep_alive="10m")
    await provider.complete(_request())

    assert captured["json"]["keep_alive"] == "10m"


async def test_usage_mapping() -> None:
    provider = _make_provider(lambda request: _ok_response(CHAT_RESPONSE_PAYLOAD))

    result = await provider.complete(_request())

    assert result.usage.prompt_tokens == 10
    assert result.usage.completion_tokens == 5
    assert result.usage.total_tokens == 15


async def test_usage_missing_total_is_computed() -> None:
    payload = dict(CHAT_RESPONSE_PAYLOAD)
    payload["usage"] = {"prompt_tokens": 10, "completion_tokens": 5}
    provider = _make_provider(lambda request: _ok_response(payload))

    result = await provider.complete(_request())

    assert result.usage.total_tokens == 15


async def test_server_error_raises_upstream_provider_error() -> None:
    provider = _make_provider(lambda request: httpx.Response(500, text="boom"))

    with pytest.raises(UpstreamProviderError):
        await provider.complete(_request())


async def test_timeout_raises_upstream_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated timeout")

    provider = _make_provider(handler)

    with pytest.raises(UpstreamProviderError):
        await provider.complete(_request())


async def test_connection_error_raises_upstream_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated connection refused")

    provider = _make_provider(handler)

    with pytest.raises(UpstreamProviderError):
        await provider.complete(_request())
