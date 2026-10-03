from __future__ import annotations

from typing import Protocol


class EventPublisher(Protocol):
    async def publish(self, event: str, data: dict) -> None: ...
