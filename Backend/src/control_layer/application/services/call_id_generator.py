from __future__ import annotations

from control_layer.domain.ports.cache_repository import CacheRepository

_SEQUENCE_KEY = "calls:seq"


class CallIdGenerator:
    def __init__(self, cache: CacheRepository) -> None:
        self._cache = cache

    async def next(self) -> str:
        sequence = await self._cache.incr(_SEQUENCE_KEY)
        return f"c_{sequence:06d}"

    async def seed(self, minimum: int) -> None:
        current = await self._cache.get(_SEQUENCE_KEY)
        if current is None or int(current) < minimum:
            await self._cache.set(_SEQUENCE_KEY, str(minimum))
