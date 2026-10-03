from __future__ import annotations

import asyncio

import pytest
from fakeredis.aioredis import FakeRedis

from control_layer.infrastructure.cache.redis_cache_repository import RedisCacheRepository


@pytest.fixture
async def repo() -> RedisCacheRepository:
    client = FakeRedis()
    try:
        yield RedisCacheRepository(client)
    finally:
        await client.aclose()


async def test_set_get_roundtrip(repo: RedisCacheRepository) -> None:
    await repo.set("k1", "v1")
    assert await repo.get("k1") == "v1"


async def test_get_missing_key_returns_none(repo: RedisCacheRepository) -> None:
    assert await repo.get("missing") is None


async def test_ttl_expiry(repo: RedisCacheRepository) -> None:
    await repo.set("k1", "v1", ttl=1)
    assert await repo.get("k1") == "v1"
    await asyncio.sleep(1.2)
    assert await repo.get("k1") is None


async def test_delete(repo: RedisCacheRepository) -> None:
    await repo.set("k1", "v1")
    await repo.delete("k1")
    assert await repo.get("k1") is None


async def test_ping_returns_true(repo: RedisCacheRepository) -> None:
    assert await repo.ping() is True


async def test_keys_by_prefix(repo: RedisCacheRepository) -> None:
    await repo.set("budget:a", "1")
    await repo.set("budget:b", "2")
    await repo.set("session:a", "3")

    keys = await repo.keys("budget:")

    assert sorted(keys) == ["budget:a", "budget:b"]


async def test_flush_by_prefix(repo: RedisCacheRepository) -> None:
    await repo.set("budget:a", "1")
    await repo.set("budget:b", "2")
    await repo.set("session:a", "3")

    await repo.flush("budget:")

    assert await repo.keys("budget:") == []
    assert await repo.get("session:a") == "3"


async def test_incr_starts_at_one(repo: RedisCacheRepository) -> None:
    assert await repo.incr("counter") == 1


async def test_incr_accumulates(repo: RedisCacheRepository) -> None:
    await repo.incr("counter")
    await repo.incr("counter")
    assert await repo.incr("counter") == 3


async def test_incr_sets_ttl_only_on_first_increment(repo: RedisCacheRepository) -> None:
    await repo.incr("counter", ttl=1)
    await repo.incr("counter", ttl=1000)
    await asyncio.sleep(1.2)

    assert await repo.get("counter") is None


class _BrokenClient:
    async def ping(self) -> bool:
        raise ConnectionError("simulated redis outage")


async def test_ping_false_on_connection_error() -> None:
    repo = RedisCacheRepository(_BrokenClient())

    assert await repo.ping() is False
