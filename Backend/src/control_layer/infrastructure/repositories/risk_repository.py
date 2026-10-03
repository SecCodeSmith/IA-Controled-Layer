from __future__ import annotations

from typing import Protocol

from control_layer.domain.models.risk import RiskProfile


class _Cache(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl: float | None = None) -> None: ...
    async def keys(self, prefix: str) -> list[str]: ...


class CacheRiskRepository:
    _PREFIX = "risk:"

    def __init__(self, cache: _Cache) -> None:
        self._cache = cache

    def _key(self, sub: str) -> str:
        return f"{self._PREFIX}{sub}"

    async def get(self, sub: str) -> RiskProfile:
        raw = await self._cache.get(self._key(sub))
        if raw is None:
            return RiskProfile(sub=sub)
        return RiskProfile.model_validate_json(raw)

    async def update(self, profile: RiskProfile) -> None:
        await self._cache.set(self._key(profile.sub), profile.model_dump_json())

    async def list_all(self) -> list[RiskProfile]:
        profiles = []
        for key in await self._cache.keys(self._PREFIX):
            raw = await self._cache.get(key)
            if raw is not None:
                profiles.append(RiskProfile.model_validate_json(raw))
        return profiles
