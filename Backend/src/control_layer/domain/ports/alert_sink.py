from __future__ import annotations

from typing import Protocol

from control_layer.domain.models.alert import Alert


class AlertSink(Protocol):
    async def emit(self, alert: Alert) -> None: ...

    async def clear(self) -> None: ...
