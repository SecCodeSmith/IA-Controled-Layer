from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from control_layer.application.services.call_id_seeding import highest_call_id
from control_layer.domain.ports.alert_sink import AlertSink
from control_layer.domain.ports.alert_store import AlertStore
from control_layer.domain.ports.audit_repository import AuditRepository

CLEARED_TARGETS = ["audit", "alerts", "alerts_xlsx", "audit_jsonl", "metrics", "feed"]


class _ResettableMetrics(Protocol):
    def reset(self) -> None: ...


class _ResettableCallIds(Protocol):
    async def reset(self, value: int) -> None: ...


class ClearLogsUseCase:
    def __init__(
        self,
        audit_repository: AuditRepository,
        alert_store: AlertStore,
        alert_sink: AlertSink,
        metrics_collector: _ResettableMetrics,
        call_ids: _ResettableCallIds,
        publish: Callable[[str, dict], Awaitable[None]],
    ) -> None:
        self._audit_repository = audit_repository
        self._alert_store = alert_store
        self._alert_sink = alert_sink
        self._metrics_collector = metrics_collector
        self._call_ids = call_ids
        self._publish = publish

    async def execute(self) -> list[str]:
        await self._audit_repository.clear()
        await self._alert_store.clear()
        await self._alert_sink.clear()
        self._metrics_collector.reset()
        await self._call_ids.reset(await highest_call_id(self._audit_repository))
        await self._publish("stats_dirty", {})
        return list(CLEARED_TARGETS)
