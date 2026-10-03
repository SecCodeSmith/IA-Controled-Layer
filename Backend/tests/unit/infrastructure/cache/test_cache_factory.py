from __future__ import annotations

import logging

import pytest
from fakeredis.aioredis import FakeRedis

from control_layer.infrastructure.cache.cache_factory import build_cache_repository
from control_layer.infrastructure.cache.in_memory_cache_repository import (
    InMemoryCacheRepository,
)
from control_layer.infrastructure.cache.redis_cache_repository import RedisCacheRepository
from control_layer.infrastructure.settings import Settings


class _FakeRedisFactory:
    def __init__(self, client: FakeRedis) -> None:
        self._client = client

    def __call__(self, url: str) -> FakeRedis:
        return self._client


class _BrokenRedisFactory:
    def __call__(self, url: str) -> object:
        class _Broken:
            async def ping(self) -> bool:
                raise ConnectionError("no redis here")

        return _Broken()


async def test_build_picks_redis_when_ping_succeeds() -> None:
    settings = Settings(_env_file=None)
    client = FakeRedis()
    try:
        result = await build_cache_repository(settings, redis_factory=_FakeRedisFactory(client))

        assert result.mode == "redis"
        assert isinstance(result.repository, RedisCacheRepository)
    finally:
        await client.aclose()


async def test_build_falls_back_to_memory_when_ping_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = Settings(_env_file=None)

    with caplog.at_level(logging.WARNING):
        result = await build_cache_repository(settings, redis_factory=_BrokenRedisFactory())

    assert result.mode == "memory"
    assert isinstance(result.repository, InMemoryCacheRepository)
    assert any("redis" in record.message.lower() for record in caplog.records)


async def test_build_falls_back_to_memory_on_timeout() -> None:
    settings = Settings(_env_file=None)

    class _HangingClient:
        async def ping(self) -> bool:
            import asyncio

            await asyncio.sleep(10)
            return True

    class _HangingFactory:
        def __call__(self, url: str) -> object:
            return _HangingClient()

    result = await build_cache_repository(
        settings, redis_factory=_HangingFactory(), ping_timeout_s=0.05
    )

    assert result.mode == "memory"
    assert isinstance(result.repository, InMemoryCacheRepository)
