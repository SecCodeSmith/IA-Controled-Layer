from __future__ import annotations

from pydantic import BaseModel

from control_layer.application.events.feed_broadcaster import FeedBroadcaster
from control_layer.application.use_cases.admin.stream_feed import StreamFeedUseCase


class _FakeStats(BaseModel):
    total_calls: int


class FakeStatsCalculator:
    def __init__(self) -> None:
        self.calls = 0

    async def compute(self) -> _FakeStats:
        self.calls += 1
        return _FakeStats(total_calls=self.calls)


async def _collect(iterator, count: int) -> list:
    results = []
    async for item in iterator:
        results.append(item)
        if len(results) == count:
            break
    return results


async def test_feed_event_is_yielded_and_triggers_a_stats_event() -> None:
    broadcaster = FeedBroadcaster()
    stats_calculator = FakeStatsCalculator()
    use_case = StreamFeedUseCase(broadcaster, stats_calculator, clock=lambda: 0.0)

    stream = use_case.stream()
    await broadcaster.publish("feed", {"call_id": "c_1"})

    events = await _collect(stream, 2)

    assert [e.event for e in events] == ["feed", "stats"]
    assert events[0].data == {"call_id": "c_1"}
    assert events[1].data == {"total_calls": 1}


async def test_alert_event_passes_through_without_a_stats_event() -> None:
    broadcaster = FeedBroadcaster()
    stats_calculator = FakeStatsCalculator()
    use_case = StreamFeedUseCase(broadcaster, stats_calculator, clock=lambda: 0.0)

    stream = use_case.stream()
    await broadcaster.publish("alert", {"id": "al_1"})
    await broadcaster.publish("feed", {"call_id": "c_1"})

    events = await _collect(stream, 3)

    assert [e.event for e in events] == ["alert", "feed", "stats"]


async def test_stats_dirty_triggers_a_stats_event_but_is_not_forwarded() -> None:
    broadcaster = FeedBroadcaster()
    stats_calculator = FakeStatsCalculator()
    use_case = StreamFeedUseCase(broadcaster, stats_calculator, clock=lambda: 0.0)

    stream = use_case.stream()
    await broadcaster.publish("stats_dirty", {})

    events = await _collect(stream, 1)

    assert [e.event for e in events] == ["stats"]


async def test_stats_event_is_throttled_to_one_per_second() -> None:
    clock_value = [0.0]
    broadcaster = FeedBroadcaster()
    stats_calculator = FakeStatsCalculator()
    use_case = StreamFeedUseCase(broadcaster, stats_calculator, clock=lambda: clock_value[0])
    stream = use_case.stream()

    await broadcaster.publish("feed", {"n": 1})
    first_batch = await _collect(stream, 2)
    assert [e.event for e in first_batch] == ["feed", "stats"]

    clock_value[0] = 0.5
    await broadcaster.publish("feed", {"n": 2})
    second_batch = await _collect(stream, 1)
    assert [e.event for e in second_batch] == ["feed"]

    clock_value[0] = 1.5
    await broadcaster.publish("feed", {"n": 3})
    third_batch = await _collect(stream, 2)
    assert [e.event for e in third_batch] == ["feed", "stats"]

    assert stats_calculator.calls == 2
