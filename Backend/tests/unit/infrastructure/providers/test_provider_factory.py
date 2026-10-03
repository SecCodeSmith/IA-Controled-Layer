from __future__ import annotations

import httpx

from control_layer.infrastructure.providers.mock_provider import MockModelProvider
from control_layer.infrastructure.providers.openai_compatible_provider import (
    OpenAICompatibleModelProvider,
)
from control_layer.infrastructure.providers.provider_factory import build_model_provider
from control_layer.infrastructure.settings import Settings


def _client_for(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_auto_picks_ollama_when_model_listed() -> None:
    settings = Settings(_env_file=None, model_provider="auto", ollama_model="qwen2.5:7b")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}, {"name": "llama3"}]})

    provider = await build_model_provider(settings, client=_client_for(handler))

    assert isinstance(provider, OpenAICompatibleModelProvider)
    assert provider.describe().name == "ollama"
    assert provider.describe().model == "qwen2.5:7b"


async def test_auto_picks_mock_when_model_not_listed() -> None:
    settings = Settings(_env_file=None, model_provider="auto", ollama_model="qwen2.5:7b")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "llama3"}]})

    provider = await build_model_provider(settings, client=_client_for(handler))

    assert isinstance(provider, MockModelProvider)


async def test_auto_picks_mock_when_ollama_unreachable() -> None:
    settings = Settings(_env_file=None, model_provider="auto")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    provider = await build_model_provider(settings, client=_client_for(handler))

    assert isinstance(provider, MockModelProvider)


async def test_explicit_mock_provider() -> None:
    settings = Settings(_env_file=None, model_provider="mock")

    provider = await build_model_provider(settings)

    assert isinstance(provider, MockModelProvider)


async def test_explicit_openai_compatible_provider() -> None:
    settings = Settings(
        _env_file=None,
        model_provider="openai_compatible",
        openai_base_url="https://api.example.com/v1",
        ollama_model="qwen2.5:7b",
    )

    provider = await build_model_provider(settings)

    assert isinstance(provider, OpenAICompatibleModelProvider)
    assert provider.describe().name == "openai_compatible"
