from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterator
from typing import Any

from control_layer.infrastructure._util import get_field


class InMemoryAlertStore:
    def __init__(self, max_size: int = 1000) -> None:
        self._alerts: deque[Any] = deque(maxlen=max_size)
        self._subscribers: list[asyncio.Queue[Any]] = []

    async def add(self, alert: Any) -> None:
        self._alerts.append(alert)
        for queue in self._subscribers:
            queue.put_nowait(alert)

    async def list_recent(
        self, limit: int, user: str | None = None, rule_id: str | None = None
    ) -> list[Any]:
        items = list(reversed(self._alerts))
        if user is not None:
            items = [a for a in items if get_field(get_field(a, "user", {}), "sub") == user]
        if rule_id is not None:
            items = [a for a in items if get_field(a, "rule_id") == rule_id]
        return items[:limit]

    def subscribe(self) -> AsyncIterator[Any]:
        queue: asyncio.Queue[Any] = asyncio.Queue()
        self._subscribers.append(queue)
        return self._generate(queue)

    async def _generate(self, queue: asyncio.Queue[Any]) -> AsyncIterator[Any]:
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers.remove(queue)
