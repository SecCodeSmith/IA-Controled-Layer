from __future__ import annotations

import time
from collections.abc import AsyncIterator, Callable
from typing import Protocol

from control_layer.application.events.feed_broadcaster import FeedBroadcaster, FeedEvent

_PASSTHROUGH_EVENTS = frozenset({"feed", "alert"})
_STATS_TRIGGER_EVENTS = frozenset({"feed", "stats_dirty"})


class _ComputesStats(Protocol):
    async def compute(self) -> object: ...


class StreamFeedUseCase:
    def __init__(
        self,
        broadcaster: FeedBroadcaster,
        stats_calculator: _ComputesStats,
        *,
        min_interval_s: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._broadcaster = broadcaster
        self._stats_calculator = stats_calculator
        self._min_interval_s = min_interval_s
        self._clock = clock

    def stream(self) -> AsyncIterator[FeedEvent]:
        subscription = self._broadcaster.subscribe()
        return self._pump(subscription)

    async def _pump(self, subscription: AsyncIterator[FeedEvent]) -> AsyncIterator[FeedEvent]:
        last_emitted: float | None = None
        async for event in subscription:
            should_passthrough = event.event in _PASSTHROUGH_EVENTS
            should_emit_stats = False
            if event.event in _STATS_TRIGGER_EVENTS:
                now = self._clock()
                if last_emitted is None or (now - last_emitted) >= self._min_interval_s:
                    should_emit_stats = True
                    last_emitted = now
            if should_passthrough:
                yield event
            if should_emit_stats:
                stats_view = await self._stats_calculator.compute()
                yield FeedEvent(event="stats", data=stats_view.model_dump(mode="json"))
