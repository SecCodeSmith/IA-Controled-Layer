from __future__ import annotations

from typing import Protocol

from control_layer.domain.models.session import SessionState


class _Cache(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl: float | None = None) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def flush(self, prefix: str) -> None: ...


class CacheSessionRepository:
    _PREFIX = "session:"

    def __init__(self, cache: _Cache) -> None:
        self._cache = cache

    def _key(self, session_id: str) -> str:
        return f"{self._PREFIX}{session_id}"

    async def get(self, session_id: str) -> SessionState:
        raw = await self._cache.get(self._key(session_id))
        if raw is None:
            return SessionState(session_id=session_id)
        return SessionState.model_validate_json(raw)

    async def save(self, state: SessionState) -> None:
        await self._cache.set(self._key(state.session_id), state.model_dump_json())

    async def clear(self, session_id: str | None = None) -> None:
        if session_id is None:
            await self._cache.flush(self._PREFIX)
        else:
            await self._cache.delete(self._key(session_id))
