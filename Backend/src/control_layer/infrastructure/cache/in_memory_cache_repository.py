from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass


@dataclass
class _Entry:
    value: str
    expires_at: float | None


class InMemoryCacheRepository:
    def __init__(self) -> None:
        self._store: dict[str, _Entry] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    async def _lock_for(self, key: str) -> asyncio.Lock:
        async with self._locks_guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock
            return lock

    def _is_expired(self, entry: _Entry) -> bool:
        return entry.expires_at is not None and entry.expires_at <= time.monotonic()

    def _expiry(self, ttl: float | None) -> float | None:
        return time.monotonic() + ttl if ttl is not None else None

    async def get(self, key: str) -> str | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if self._is_expired(entry):
            self._store.pop(key, None)
            return None
        return entry.value

    async def set(self, key: str, value: str, ttl: float | None = None) -> None:
        self._store[key] = _Entry(value=value, expires_at=self._expiry(ttl))

    async def incr(self, key: str, ttl: float | None = None) -> int:
        lock = await self._lock_for(key)
        async with lock:
            entry = self._store.get(key)
            if entry is not None and self._is_expired(entry):
                entry = None
            if entry is None:
                new_value = 1
                self._store[key] = _Entry(
                    value=str(new_value), expires_at=self._expiry(ttl)
                )
            else:
                new_value = int(entry.value) + 1
                entry.value = str(new_value)
            return new_value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def ping(self) -> bool:
        return True

    async def keys(self, prefix: str) -> list[str]:
        result = []
        for key, entry in list(self._store.items()):
            if not key.startswith(prefix):
                continue
            if self._is_expired(entry):
                continue
            result.append(key)
        return result

    async def flush(self, prefix: str) -> None:
        for key in list(self._store.keys()):
            if key.startswith(prefix):
                self._store.pop(key, None)
