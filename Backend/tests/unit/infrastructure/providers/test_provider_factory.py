from __future__ import annotations

import httpx
import pytest

from control_layer.infrastructure.providers.mock_provider import MockModelProvider
from control_layer.infrastructure.providers.openai_compatible_provider import (
    OpenAICompatibleModelProvider,
)
from control_layer.infrastructure.providers.provider_factory import (
    build_model_provider,
    build_provider_for,
)
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


def test_build_provider_for_each_known_provider() -> None:
    settings = Settings(ollama_base_url="http://ollama:11434", openai_base_url=None)

    ollama = build_provider_for(settings, "ollama", "gemma4:latest")
    mock = build_provider_for(settings, "mock", "mock")
    compat = build_provider_for(settings, "openai_compatible", "m1")

    assert (ollama.describe().name, ollama.describe().model) == ("ollama", "gemma4:latest")
    assert ollama._base_url == "http://ollama:11434/v1"
    assert mock.describe().name == "mock"
    assert (compat.describe().name, compat.describe().model) == ("openai_compatible", "m1")


def test_build_provider_for_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError):
        build_provider_for(Settings(), "bogus", "x")
