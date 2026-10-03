from __future__ import annotations

import asyncio

import pytest

from control_layer.infrastructure.cache.in_memory_cache_repository import (
    InMemoryCacheRepository,
)


@pytest.fixture
def repo() -> InMemoryCacheRepository:
    return InMemoryCacheRepository()


async def test_set_get_roundtrip(repo: InMemoryCacheRepository) -> None:
    await repo.set("k1", "v1")
    assert await repo.get("k1") == "v1"


async def test_get_missing_key_returns_none(repo: InMemoryCacheRepository) -> None:
    assert await repo.get("missing") is None


async def test_ttl_expiry(repo: InMemoryCacheRepository) -> None:
    await repo.set("k1", "v1", ttl=0.05)
    assert await repo.get("k1") == "v1"
    await asyncio.sleep(0.08)
    assert await repo.get("k1") is None


async def test_delete(repo: InMemoryCacheRepository) -> None:
    await repo.set("k1", "v1")
    await repo.delete("k1")
    assert await repo.get("k1") is None


async def test_delete_missing_key_is_noop(repo: InMemoryCacheRepository) -> None:
    await repo.delete("missing")


async def test_ping_returns_true(repo: InMemoryCacheRepository) -> None:
    assert await repo.ping() is True


async def test_keys_by_prefix(repo: InMemoryCacheRepository) -> None:
    await repo.set("budget:a", "1")
    await repo.set("budget:b", "2")
    await repo.set("session:a", "3")

    keys = await repo.keys("budget:")

    assert sorted(keys) == ["budget:a", "budget:b"]


async def test_keys_excludes_expired(repo: InMemoryCacheRepository) -> None:
    await repo.set("budget:a", "1", ttl=0.05)
    await asyncio.sleep(0.08)

    assert await repo.keys("budget:") == []


async def test_flush_by_prefix(repo: InMemoryCacheRepository) -> None:
    await repo.set("budget:a", "1")
    await repo.set("budget:b", "2")
    await repo.set("session:a", "3")

    await repo.flush("budget:")

    assert await repo.keys("budget:") == []
    assert await repo.get("session:a") == "3"


async def test_incr_starts_at_one(repo: InMemoryCacheRepository) -> None:
    assert await repo.incr("counter") == 1


async def test_incr_accumulates(repo: InMemoryCacheRepository) -> None:
    await repo.incr("counter")
    await repo.incr("counter")
    assert await repo.incr("counter") == 3


async def test_incr_sets_ttl_only_on_first_increment(repo: InMemoryCacheRepository) -> None:
    await repo.incr("counter", ttl=0.05)
    await repo.incr("counter", ttl=1000)
    await asyncio.sleep(0.08)

    assert await repo.get("counter") is None


async def test_incr_is_atomic_under_concurrency(repo: InMemoryCacheRepository) -> None:
    async def bump() -> None:
        await repo.incr("concurrent")

    await asyncio.gather(*(bump() for _ in range(200)))

    assert await repo.get("concurrent") == "200"
