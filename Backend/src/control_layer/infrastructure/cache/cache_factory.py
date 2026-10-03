from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Protocol

from redis.asyncio import Redis

from control_layer.infrastructure.cache.in_memory_cache_repository import (
    InMemoryCacheRepository,
)
from control_layer.infrastructure.cache.redis_cache_repository import RedisCacheRepository
from control_layer.infrastructure.settings import Settings

logger = logging.getLogger(__name__)


class SupportsCacheRepository(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl: float | None = None) -> None: ...
    async def incr(self, key: str, ttl: float | None = None) -> int: ...
    async def delete(self, key: str) -> None: ...
    async def ping(self) -> bool: ...
    async def keys(self, prefix: str) -> list[str]: ...
    async def flush(self, prefix: str) -> None: ...


@dataclass(frozen=True)
class CacheBuildResult:
    repository: SupportsCacheRepository
    mode: str


def _default_redis_factory(url: str) -> Any:
    return Redis.from_url(url)


async def build_cache_repository(
    settings: Settings,
    redis_factory: Any = _default_redis_factory,
    ping_timeout_s: float = 1.0,
) -> CacheBuildResult:
    try:
        client = redis_factory(settings.redis_url)
        ok = await asyncio.wait_for(client.ping(), timeout=ping_timeout_s)
        if not ok:
            raise ConnectionError("redis ping returned falsy")
        return CacheBuildResult(repository=RedisCacheRepository(client), mode="redis")
    except Exception as exc:
        logger.warning(
            "Redis unavailable at %s (%s); falling back to in-memory cache",
            settings.redis_url,
            exc,
        )
        return CacheBuildResult(repository=InMemoryCacheRepository(), mode="memory")
