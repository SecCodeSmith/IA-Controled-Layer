from __future__ import annotations

from control_layer.domain.models.session import SessionState
from control_layer.infrastructure.cache.in_memory_cache_repository import (
    InMemoryCacheRepository,
)
from control_layer.infrastructure.repositories.session_repository import (
    CacheSessionRepository,
)


async def test_get_missing_returns_fresh_empty_state() -> None:
    repo = CacheSessionRepository(InMemoryCacheRepository())

    state = await repo.get("s-1")

    assert state.session_id == "s-1"
    assert state.tags_seen == []
    assert state.tainted is False
    assert state.call_hashes == []


async def test_save_then_get_roundtrip() -> None:
    repo = CacheSessionRepository(InMemoryCacheRepository())
    state = SessionState(session_id="s-1", tags_seen=["read_external"], tainted=True)

    await repo.save(state)
    fetched = await repo.get("s-1")

    assert fetched.tainted is True
    assert fetched.tags_seen == ["read_external"]


async def test_clear_one_session() -> None:
    repo = CacheSessionRepository(InMemoryCacheRepository())
    await repo.save(SessionState(session_id="s-1", tainted=True))
    await repo.save(SessionState(session_id="s-2", tainted=True))

    await repo.clear("s-1")

    assert (await repo.get("s-1")).tainted is False
    assert (await repo.get("s-2")).tainted is True


async def test_clear_all_sessions() -> None:
    repo = CacheSessionRepository(InMemoryCacheRepository())
    await repo.save(SessionState(session_id="s-1", tainted=True))
    await repo.save(SessionState(session_id="s-2", tainted=True))

    await repo.clear()

    assert (await repo.get("s-1")).tainted is False
    assert (await repo.get("s-2")).tainted is False
