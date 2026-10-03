from __future__ import annotations

from control_layer.domain.ports.cache_repository import CacheRepository

_SEQUENCE_KEY = "calls:seq"


class CallIdGenerator:
    def __init__(self, cache: CacheRepository) -> None:
        self._cache = cache

    async def next(self) -> str:
        sequence = await self._cache.incr(_SEQUENCE_KEY)
        return f"c_{sequence:06d}"
