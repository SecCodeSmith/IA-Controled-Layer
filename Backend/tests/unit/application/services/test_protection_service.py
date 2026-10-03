from __future__ import annotations

from control_layer.application.services.protection_service import (
    ProtectionService,
    current_protection,
)
from control_layer.domain.models.enums import ProtectionMode
from control_layer.infrastructure.cache.in_memory_cache_repository import InMemoryCacheRepository


async def _service_with_decision() -> tuple[ProtectionService, InMemoryCacheRepository]:
    cache = InMemoryCacheRepository()
    await cache.set("decision:1:abc", "[]")
    return ProtectionService(cache), cache


async def test_defaults_to_enforce_without_overrides() -> None:
    service = ProtectionService(InMemoryCacheRepository())

    assert await service.get_mode() is ProtectionMode.enforce
    assert await service.get_rule_overrides() == {}


async def test_set_mode_persists_and_flushes_decisions() -> None:
    service, cache = await _service_with_decision()

    await service.set_mode(ProtectionMode.monitor)

    assert await service.get_mode() is ProtectionMode.monitor
    assert await cache.get("decision:1:abc") is None
    assert await cache.get("protection:mode") == "monitor"


async def test_unknown_stored_mode_falls_back_to_enforce() -> None:
    cache = InMemoryCacheRepository()
    await cache.set("protection:mode", "bogus")

    assert await ProtectionService(cache).get_mode() is ProtectionMode.enforce


async def test_rule_overrides_accumulate_and_flush_decisions() -> None:
    service, cache = await _service_with_decision()

    await service.set_rule_override("pii_masking", False)
    await cache.set("decision:1:abc", "[]")
    await service.set_rule_override("loop_guard", True)

    assert await service.get_rule_overrides() == {"pii_masking": False, "loop_guard": True}
    assert await cache.get("decision:1:abc") is None


async def test_clear_overrides_keeps_the_mode() -> None:
    service, cache = await _service_with_decision()
    await service.set_mode(ProtectionMode.off)
    await service.set_rule_override("pii_masking", False)
    await cache.set("decision:1:abc", "[]")

    await service.clear_overrides()

    assert await service.get_rule_overrides() == {}
    assert await service.get_mode() is ProtectionMode.off
    assert await cache.get("decision:1:abc") is None


async def test_reset_restores_mode_and_overrides() -> None:
    service, _ = await _service_with_decision()
    await service.set_mode(ProtectionMode.off)
    await service.set_rule_override("pii_masking", False)

    await service.reset()

    assert await service.get_mode() is ProtectionMode.enforce
    assert await service.get_rule_overrides() == {}


async def test_current_protection_handles_a_missing_service() -> None:
    assert (await current_protection(None)).mode is ProtectionMode.enforce
    service = ProtectionService(InMemoryCacheRepository())
    await service.set_mode(ProtectionMode.monitor)
    assert (await current_protection(service)).mode is ProtectionMode.monitor
