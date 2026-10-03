from __future__ import annotations

import asyncio

import pytest

from control_layer.application.events.feed_broadcaster import FeedBroadcaster, FeedEvent


async def test_publish_fans_out_to_every_subscriber() -> None:
    broadcaster = FeedBroadcaster()
    sub_a = broadcaster.subscribe()
    sub_b = broadcaster.subscribe()

    await broadcaster.publish("feed", {"call_id": "c_1"})

    event_a = await sub_a.__anext__()
    event_b = await sub_b.__anext__()

    assert event_a == FeedEvent(event="feed", data={"call_id": "c_1"})
    assert event_b == FeedEvent(event="feed", data={"call_id": "c_1"})


async def test_subscriber_registered_immediately_on_subscribe() -> None:
    broadcaster = FeedBroadcaster()

    broadcaster.subscribe()

    assert broadcaster.subscriber_count == 1


async def test_subscriber_queue_drops_oldest_on_overflow() -> None:
    broadcaster = FeedBroadcaster(maxsize=2)
    subscription = broadcaster.subscribe()

    await broadcaster.publish("feed", {"n": 1})
    await broadcaster.publish("feed", {"n": 2})
    await broadcaster.publish("feed", {"n": 3})

    first = await subscription.__anext__()
    second = await subscription.__anext__()

    assert first.data == {"n": 2}
    assert second.data == {"n": 3}


async def test_close_ends_all_subscriber_iterators() -> None:
    broadcaster = FeedBroadcaster()
    subscription = broadcaster.subscribe()

    await broadcaster.close()

    with pytest.raises(StopAsyncIteration):
        await subscription.__anext__()


async def test_publish_after_close_does_not_raise() -> None:
    broadcaster = FeedBroadcaster()
    broadcaster.subscribe()

    await broadcaster.close()

    await broadcaster.publish("feed", {"n": 1})


async def test_cancelling_a_subscriber_task_removes_it_from_subscriber_list() -> None:
    broadcaster = FeedBroadcaster()

    async def consume_forever() -> None:
        async for _event in broadcaster.subscribe():
            pass

    task = asyncio.create_task(consume_forever())
    await asyncio.sleep(0)
    assert broadcaster.subscriber_count == 1

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert broadcaster.subscriber_count == 0
