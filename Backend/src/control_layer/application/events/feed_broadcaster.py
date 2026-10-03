from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass

_SENTINEL = object()


@dataclass(frozen=True)
class FeedEvent:
    event: str
    data: dict


class FeedBroadcaster:
    def __init__(self, maxsize: int = 100) -> None:
        self._maxsize = maxsize
        self._subscribers: list[asyncio.Queue] = []
        self._closed = False

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    async def publish(self, event: str, data: dict) -> None:
        if self._closed:
            return
        feed_event = FeedEvent(event=event, data=data)
        for queue in list(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(feed_event)
            except asyncio.QueueFull:
                pass

    def subscribe(self) -> AsyncIterator[FeedEvent]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._maxsize)
        self._subscribers.append(queue)
        return self._consume(queue)

    async def _consume(self, queue: asyncio.Queue) -> AsyncIterator[FeedEvent]:
        try:
            while True:
                item = await queue.get()
                if item is _SENTINEL:
                    return
                yield item
        finally:
            if queue in self._subscribers:
                self._subscribers.remove(queue)

    async def close(self) -> None:
        self._closed = True
        subscribers = list(self._subscribers)
        for queue in subscribers:
            await queue.put(_SENTINEL)
