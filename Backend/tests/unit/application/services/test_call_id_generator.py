from __future__ import annotations

from control_layer.application.services.call_id_generator import CallIdGenerator


class _FakeCache:
    def __init__(self) -> None:
        self._counters: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return str(self._counters[key]) if key in self._counters else None

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        self._counters[key] = int(value)

    async def incr(self, key: str, ttl: int | None = None) -> int:
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]

    async def delete(self, key: str) -> None:
        self._counters.pop(key, None)

    async def ping(self) -> bool:
        return True

    async def keys(self, prefix: str) -> list[str]:
        return [k for k in self._counters if k.startswith(prefix)]

    async def flush(self, prefix: str) -> None:
        for k in list(self._counters):
            if k.startswith(prefix):
                del self._counters[k]


async def test_ids_are_sequential_and_zero_padded() -> None:
    generator = CallIdGenerator(_FakeCache())
    assert await generator.next() == "c_000001"
    assert await generator.next() == "c_000002"
    assert await generator.next() == "c_000003"


async def test_uses_calls_seq_key() -> None:
    cache = _FakeCache()
    generator = CallIdGenerator(cache)
    await generator.next()
    assert "calls:seq" in cache._counters
