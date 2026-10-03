from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class CompositeAlertSink:
    def __init__(self, sinks: list[Any]) -> None:
        self._sinks = sinks

    async def emit(self, alert: Any) -> None:
        for sink in self._sinks:
            try:
                await sink.emit(alert)
            except Exception as exc:
                logger.error(
                    "Alert sink %r failed to emit alert: %s", sink, exc, exc_info=True
                )
