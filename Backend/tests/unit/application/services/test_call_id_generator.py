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
    assert "audit:call_seq" in cache._counters


async def test_seed_raises_counter_so_next_id_follows_minimum() -> None:
    generator = CallIdGenerator(_FakeCache())
    await generator.seed(41)
    assert await generator.next() == "c_000042"


async def test_seed_never_lowers_an_existing_higher_counter() -> None:
    generator = CallIdGenerator(_FakeCache())
    for _ in range(5):
        await generator.next()
    await generator.seed(2)
    assert await generator.next() == "c_000006"


async def test_flushing_the_calls_prefix_keeps_the_sequence() -> None:
    cache = _FakeCache()
    generator = CallIdGenerator(cache)
    await generator.next()
    await generator.next()
    await cache.incr("calls:session-1")

    await cache.flush("calls:")

    assert await generator.next() == "c_000003"
