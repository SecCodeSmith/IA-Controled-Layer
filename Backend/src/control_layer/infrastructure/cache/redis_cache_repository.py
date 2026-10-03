from __future__ import annotations

from typing import Protocol


class _RedisClient(Protocol):
    async def get(self, key: str) -> bytes | str | None: ...
    async def set(self, key: str, value: str, ex: int | None = None) -> object: ...
    async def incr(self, key: str) -> int: ...
    async def expire(self, key: str, seconds: int) -> object: ...
    async def delete(self, key: str) -> object: ...
    async def ping(self) -> object: ...
    async def scan_iter(self, match: str | None = None): ...
    def close(self) -> object: ...


class RedisCacheRepository:
    def __init__(self, client: _RedisClient) -> None:
        self._client = client

    @staticmethod
    def _decode(value: bytes | str | None) -> str | None:
        if value is None:
            return None
        return value.decode() if isinstance(value, bytes) else value

    async def get(self, key: str) -> str | None:
        return self._decode(await self._client.get(key))

    async def set(self, key: str, value: str, ttl: float | None = None) -> None:
        ex = int(ttl) if ttl is not None else None
        await self._client.set(key, value, ex=ex)

    async def incr(self, key: str, ttl: float | None = None) -> int:
        new_value = await self._client.incr(key)
        if new_value == 1 and ttl is not None:
            await self._client.expire(key, int(ttl))
        return new_value

    async def delete(self, key: str) -> None:
        await self._client.delete(key)

    async def ping(self) -> bool:
        try:
            await self._client.ping()
            return True
        except Exception:
            return False

    async def keys(self, prefix: str) -> list[str]:
        result = []
        async for raw_key in self._client.scan_iter(match=f"{prefix}*"):
            decoded = self._decode(raw_key)
            if decoded is not None:
                result.append(decoded)
        return result

    async def flush(self, prefix: str) -> None:
        for key in await self.keys(prefix):
            await self.delete(key)
