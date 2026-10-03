from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from control_layer.domain.models.alert import Alert


class AlertStore(Protocol):
    async def add(self, alert: Alert) -> None: ...

    async def list_recent(self, limit: int = 100) -> list[Alert]: ...

    def subscribe(self) -> AsyncIterator[Alert]: ...
