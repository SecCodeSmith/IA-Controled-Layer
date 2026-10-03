from __future__ import annotations

import logging
from typing import Any

import httpx

from control_layer.infrastructure.providers.mock_provider import MockModelProvider
from control_layer.infrastructure.providers.openai_compatible_provider import (
    OpenAICompatibleModelProvider,
)
from control_layer.infrastructure.settings import Settings

logger = logging.getLogger(__name__)


async def _ollama_lists_model(
    base_url: str, model: str, client: httpx.AsyncClient
) -> bool:
    response = await client.get(f"{base_url}/api/tags")
    response.raise_for_status()
    models = [entry.get("name") for entry in response.json().get("models", [])]
    return model in models


async def build_model_provider(
    settings: Settings, client: httpx.AsyncClient | None = None
) -> Any:
    owns_client = client is None
    http_client = client or httpx.AsyncClient()

    try:
        if settings.model_provider == "mock":
            logger.info("Model provider explicitly set to mock")
            return MockModelProvider()

        if settings.model_provider == "openai_compatible":
            base_url = settings.openai_base_url or f"{settings.ollama_base_url}/v1"
            logger.info("Model provider explicitly set to openai_compatible at %s", base_url)
            return OpenAICompatibleModelProvider(
                base_url=base_url,
                model=settings.ollama_model,
                provider_name="openai_compatible",
                api_key=settings.openai_api_key,
            )

        try:
            if await _ollama_lists_model(
                settings.ollama_base_url, settings.ollama_model, http_client
            ):
                logger.info(
                    "Auto-detected Ollama model %s at %s; using it",
                    settings.ollama_model,
                    settings.ollama_base_url,
                )
                return OpenAICompatibleModelProvider(
                    base_url=f"{settings.ollama_base_url}/v1",
                    model=settings.ollama_model,
                    provider_name="ollama",
                )
            logger.warning(
                "Ollama model %s not listed at %s; falling back to mock provider",
                settings.ollama_model,
                settings.ollama_base_url,
            )
        except Exception as exc:
            logger.warning(
                "Ollama unreachable at %s (%s); falling back to mock provider",
                settings.ollama_base_url,
                exc,
            )
        return MockModelProvider()
    finally:
        if owns_client:
            await http_client.aclose()


def build_provider_for(settings: Settings, provider_name: str, model: str) -> Any:
    if provider_name == "mock":
        return MockModelProvider()
    if provider_name == "ollama":
        return OpenAICompatibleModelProvider(
            base_url=f"{settings.ollama_base_url}/v1",
            model=model,
            provider_name="ollama",
        )
    if provider_name == "openai_compatible":
        return OpenAICompatibleModelProvider(
            base_url=settings.openai_base_url or f"{settings.ollama_base_url}/v1",
            model=model,
            provider_name="openai_compatible",
            api_key=settings.openai_api_key,
        )
    raise ValueError(f"unknown model provider: {provider_name}")
