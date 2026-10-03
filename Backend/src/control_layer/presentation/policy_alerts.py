from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from control_layer.domain.models.alert import Alert, AlertUserRef
from control_layer.domain.models.enums import CallStatus, Role, Severity, StageName

_SYSTEM_USER = AlertUserRef(sub="system", name="System", role=Role.developer)


class PolicyReloadNotifier:
    def __init__(
        self,
        policy_repository: Any,
        alert_sink: Any,
        alert_store: Any,
        publish: Callable[[str, dict], Awaitable[None]],
    ) -> None:
        self._policy_repository = policy_repository
        self._alert_sink = alert_sink
        self._alert_store = alert_store
        self._publish = publish
        self._last_status = "LOADED"
        self._last_error: str | None = None

    async def reload(self) -> None:
        await self._policy_repository.reload()
        await self.observe()

    async def observe(self) -> None:
        status = await self._policy_repository.status()
        state, error = status["status"], status.get("error")
        if state == "ERROR" and (self._last_status != "ERROR" or error != self._last_error):
            await self._emit(
                CallStatus.BLOCKED,
                Severity.high,
                f"Policy reload failed, last good policy still enforced: {error}",
                [str(error)] if error else [],
            )
        elif state == "LOADED" and self._last_status == "ERROR":
            await self._emit(
                CallStatus.ALLOWED,
                Severity.low,
                f"Policy reloaded successfully (version {status.get('version')})",
                [],
            )
        self._last_status, self._last_error = state, error

    async def _emit(
        self, status: CallStatus, severity: Severity, reason: str, evidence: list[str]
    ) -> None:
        alert = Alert(
            id=f"al_{uuid.uuid4().hex[:12]}",
            created_at=datetime.now(UTC),
            call_id="policy",
            user=_SYSTEM_USER,
            status=status,
            stage=StageName.policy,
            rule_id="policy_reload",
            severity=severity,
            owasp=[],
            reason=reason,
            evidence=evidence,
        )
        await self._alert_sink.emit(alert)
        await self._alert_store.add(alert)
        await self._publish("alert", alert.model_dump(mode="json"))
