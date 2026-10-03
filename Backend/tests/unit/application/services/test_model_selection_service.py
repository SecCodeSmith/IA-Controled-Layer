from __future__ import annotations

import pytest

from control_layer.application.services.model_selection_service import ModelSelectionService
from control_layer.domain.exceptions import ModelNotAvailableError
from control_layer.domain.models.model_info import ModelInfo
from control_layer.domain.models.provider import ProviderInfo
from control_layer.infrastructure.cache.in_memory_cache_repository import InMemoryCacheRepository
from control_layer.infrastructure.providers.switchable_provider import SwitchableModelProvider


class _NamedProvider:
    def __init__(self, name: str, model: str) -> None:
        self._info = ProviderInfo(name=name, model=model)

    def describe(self) -> ProviderInfo:
        return self._info

    async def complete(self, request: object) -> object:
        raise NotImplementedError


class _Directory:
    def __init__(self, models: list[ModelInfo]) -> None:
        self.models = models

    async def list_models(self) -> list[ModelInfo]:
        return self.models


class _Policy:
    def __init__(self, allowed: list[str]) -> None:
        self._allowed = allowed

    async def current(self) -> object:
        class _Models:
            allowed = self._allowed

        class _Document:
            models = _Models()

        return _Document()


_MODELS = [
    ModelInfo(provider="ollama", model="qwen2.5:7b", size_gb=4.7),
    ModelInfo(provider="ollama", model="gemma4:latest", size_gb=6.6),
    ModelInfo(provider="mock", model="mock"),
]


def _service(
    cache: InMemoryCacheRepository | None = None, models: list[ModelInfo] | None = None
) -> tuple[ModelSelectionService, SwitchableModelProvider, InMemoryCacheRepository]:
    switchable = SwitchableModelProvider(_NamedProvider("mock", "mock"))
    resolved_cache = cache or InMemoryCacheRepository()
    service = ModelSelectionService(
        switchable,
        _Directory(_MODELS if models is None else models),
        _NamedProvider,
        _Policy(["qwen2.5:7b", "mock"]),  # type: ignore[arg-type]
        resolved_cache,
    )
    return service, switchable, resolved_cache


async def test_list_models_flags_allowlisted_models_and_reports_the_active_one() -> None:
    service, _, _ = _service()

    listing = await service.list_models()

    assert listing.active == ProviderInfo(name="mock", model="mock")
    flags = {(m.provider, m.model): m.allowed for m in listing.available}
    assert flags == {
        ("ollama", "qwen2.5:7b"): True,
        ("ollama", "gemma4:latest"): False,
        ("mock", "mock"): True,
    }
    assert listing.available[0].size_gb == 4.7
    assert listing.available[2].size_gb is None


async def test_select_switches_describe_and_stores_the_choice() -> None:
    service, switchable, cache = _service()

    active = await service.select("ollama", "gemma4:latest")

    assert active == ProviderInfo(name="ollama", model="gemma4:latest")
    assert switchable.describe() == active
    assert "gemma4:latest" in (await cache.get("models:active") or "")


async def test_select_unknown_model_raises_and_keeps_the_active_provider() -> None:
    service, switchable, cache = _service()

    with pytest.raises(ModelNotAvailableError):
        await service.select("ollama", "nope:1b")

    assert switchable.describe().name == "mock"
    assert await cache.get("models:active") is None


async def test_restore_reapplies_the_stored_selection_when_still_listed() -> None:
    cache = InMemoryCacheRepository()
    first, _, _ = _service(cache)
    await first.select("ollama", "qwen2.5:7b")

    second, switchable, _ = _service(cache)
    await second.restore()

    assert switchable.describe() == ProviderInfo(name="ollama", model="qwen2.5:7b")


async def test_restore_ignores_a_selection_that_is_no_longer_listed() -> None:
    cache = InMemoryCacheRepository()
    first, _, _ = _service(cache)
    await first.select("ollama", "qwen2.5:7b")

    second, switchable, _ = _service(cache, models=[ModelInfo(provider="mock", model="mock")])
    await second.restore()

    assert switchable.describe().name == "mock"


async def test_restore_ignores_garbage_in_the_cache() -> None:
    cache = InMemoryCacheRepository()
    await cache.set("models:active", "{not json")
    service, switchable, _ = _service(cache)

    await service.restore()

    assert switchable.describe().name == "mock"
