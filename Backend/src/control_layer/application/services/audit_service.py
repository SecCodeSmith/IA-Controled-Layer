from __future__ import annotations

from control_layer.application.services.alert_factory import AlertFactory
from control_layer.domain.models.alert import Alert
from control_layer.domain.models.audit import CallRecord
from control_layer.domain.models.decision import Decision
from control_layer.domain.ports.alert_sink import AlertSink
from control_layer.domain.ports.alert_store import AlertStore
from control_layer.domain.ports.audit_repository import AuditRepository
from control_layer.domain.ports.event_publisher import EventPublisher
from control_layer.domain.ports.policy_repository import PolicyRepository


class AuditService:
    def __init__(
        self,
        audit_repository: AuditRepository,
        alert_sink: AlertSink,
        alert_store: AlertStore,
        event_publisher: EventPublisher,
        alert_factory: AlertFactory,
        policy_repository: PolicyRepository,
    ) -> None:
        self._audit_repository = audit_repository
        self._alert_sink = alert_sink
        self._alert_store = alert_store
        self._event_publisher = event_publisher
        self._alert_factory = alert_factory
        self._policy_repository = policy_repository

    async def record(self, call: CallRecord, decision: Decision) -> Alert | None:
        await self._audit_repository.append(call)

        alert = self._alert_factory.build(call, decision)
        if alert is not None:
            await self._alert_sink.emit(alert)
            await self._alert_store.add(alert)

        await self._event_publisher.publish("feed", self._feed_row(call))
        if alert is not None:
            await self._event_publisher.publish("alert", alert.model_dump(mode="json"))
        await self._event_publisher.publish("stats_dirty", {})

        return alert

    @staticmethod
    def _feed_row(call: CallRecord) -> dict:
        return {
            "call_id": call.call_id,
            "time": call.timestamp.isoformat(),
            "user": {
                "sub": call.identity.sub,
                "name": call.identity.name,
                "role": call.identity.role.value,
            },
            "kind": call.kind.value,
            "target": call.target,
            "status": call.decision.status.value,
            "stage": call.decision.stage.value if call.decision.stage else None,
            "rule_id": call.decision.rule_id,
            "reason": call.decision.reason,
            "proxy_latency_ms": call.latency.proxy_ms,
            "upstream_latency_ms": call.latency.upstream_ms,
            "overhead_ms": call.latency.overhead_ms,
        }
