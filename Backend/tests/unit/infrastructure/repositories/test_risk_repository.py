from __future__ import annotations

from control_layer.domain.models.risk import RiskProfile
from control_layer.infrastructure.cache.in_memory_cache_repository import (
    InMemoryCacheRepository,
)
from control_layer.infrastructure.repositories.risk_repository import CacheRiskRepository


async def test_get_missing_returns_zeroed_profile() -> None:
    repo = CacheRiskRepository(InMemoryCacheRepository())

    profile = await repo.get("anna.kowalska")

    assert profile.sub == "anna.kowalska"
    assert profile.score == 0
    assert profile.level == "low"
    assert profile.signals == []


async def test_update_then_get_roundtrip() -> None:
    repo = CacheRiskRepository(InMemoryCacheRepository())
    profile = RiskProfile(sub="anna.kowalska", score=42, level="high", signals=["burst"])

    await repo.update(profile)
    fetched = await repo.get("anna.kowalska")

    assert fetched.score == 42
    assert fetched.level == "high"
    assert fetched.signals == ["burst"]


async def test_list_all_returns_every_profile() -> None:
    repo = CacheRiskRepository(InMemoryCacheRepository())
    await repo.update(RiskProfile(sub="anna.kowalska", score=10))
    await repo.update(RiskProfile(sub="marek.nowak", score=20))

    profiles = await repo.list_all()

    assert {p.sub for p in profiles} == {"anna.kowalska", "marek.nowak"}
