from __future__ import annotations

import json
from collections.abc import Callable
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from control_layer.domain.exceptions import ModelNotAvailableError
from control_layer.domain.models.model_info import ModelInfo
from control_layer.domain.models.provider import ProviderInfo
from control_layer.domain.ports.cache_repository import CacheRepository
from control_layer.domain.ports.model_directory import ModelDirectory
from control_layer.domain.ports.model_provider import ModelProvider
from control_layer.domain.ports.policy_repository import PolicyRepository

ACTIVE_MODEL_KEY = "models:active"


class SwitchableProvider(ModelProvider, Protocol):
    def switch(self, provider: ModelProvider) -> None: ...


class AvailableModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    model: str
    allowed: bool
    size_gb: float | None = None


class ModelListing(BaseModel):
    model_config = ConfigDict(frozen=True)

    active: ProviderInfo
    available: list[AvailableModel]


class ModelSelectionService:
    def __init__(
        self,
        switchable: SwitchableProvider,
        directory: ModelDirectory,
        provider_factory: Callable[[str, str], ModelProvider],
        policy_repository: PolicyRepository,
        cache: CacheRepository,
    ) -> None:
        self._switchable = switchable
        self._directory = directory
        self._provider_factory = provider_factory
        self._policy_repository = policy_repository
        self._cache = cache

    async def list_models(self) -> ModelListing:
        allowed = set((await self._policy_repository.current()).models.allowed)
        return ModelListing(
            active=self._switchable.describe(),
            available=[
                AvailableModel(
                    provider=info.provider,
                    model=info.model,
                    allowed=info.model in allowed,
                    size_gb=info.size_gb,
                )
                for info in await self._directory.list_models()
            ],
        )

    async def select(self, provider: str, model: str) -> ProviderInfo:
        if not await self._is_listed(provider, model):
            raise ModelNotAvailableError(provider, model)
        self._switchable.switch(self._provider_factory(provider, model))
        await self._cache.set(ACTIVE_MODEL_KEY, json.dumps({"provider": provider, "model": model}))
        return self._switchable.describe()

    async def restore(self) -> None:
        raw = await self._cache.get(ACTIVE_MODEL_KEY)
        if raw is None:
            return
        try:
            saved = json.loads(raw)
            provider, model = str(saved["provider"]), str(saved["model"])
        except (ValueError, KeyError, TypeError):
            return
        if await self._is_listed(provider, model):
            self._switchable.switch(self._provider_factory(provider, model))

    async def _is_listed(self, provider: str, model: str) -> bool:
        listed: list[ModelInfo] = await self._directory.list_models()
        return any(info.provider == provider and info.model == model for info in listed)
