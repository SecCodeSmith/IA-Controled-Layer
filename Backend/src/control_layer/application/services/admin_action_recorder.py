from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from control_layer.application.services.audit_service import AuditService
from control_layer.domain.models.audit import (
    CallDecisionInfo,
    CallLatency,
    CallRecord,
    CallRequestInfo,
    CallResponseInfo,
    TokensInfo,
)
from control_layer.domain.models.decision import Decision, Violation
from control_layer.domain.models.enums import (
    CallKind,
    CallStatus,
    Role,
    RuleAction,
    Severity,
    StageName,
)
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.provider import ProviderInfo

ADMIN_IDENTITY = Identity(
    sub="admin",
    name="Administrator",
    role=Role.admin,
    location="-",
    region="-",
    agent_id="admin-console",
)
_PROVIDER = ProviderInfo(name="control-layer", model="-")
_CRITICAL_REASON_MARKER = "set to off"


class AdminActionRecorder:
    def __init__(
        self,
        audit_service: AuditService,
        call_ids: Any,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._audit_service = audit_service
        self._call_ids = call_ids
        self._clock = clock

    async def record(
        self,
        action: str,
        *,
        details: dict[str, Any],
        loosening: bool,
        actor: str = "admin",
    ) -> CallRecord:
        reason = str(details.get("reason") or action)
        status = CallStatus.FLAGGED if loosening else CallStatus.ALLOWED
        call = CallRecord(
            call_id=await self._call_ids.next(),
            timestamp=self._clock(),
            identity=ADMIN_IDENTITY.model_copy(update={"sub": actor}),
            kind=CallKind.admin,
            target=action,
            decision=CallDecisionInfo(
                status=status,
                stage=StageName.audit,
                rule_id=action,
                reason=reason,
            ),
            request=CallRequestInfo(summary=reason, payload={"actor": actor, **details}),
            response=CallResponseInfo(),
            tokens=TokensInfo(),
            latency=CallLatency(proxy_ms=0.0, upstream_ms=0.0),
            provider=_PROVIDER,
        )
        await self._audit_service.record(call, self._decision(action, reason, status))
        return call

    @staticmethod
    def _decision(action: str, reason: str, status: CallStatus) -> Decision:
        if status == CallStatus.ALLOWED:
            return Decision(status=status, action=RuleAction.allow)
        severity = Severity.critical if _CRITICAL_REASON_MARKER in reason else Severity.high
        violation = Violation(
            stage=StageName.audit,
            rule_id=action,
            action=RuleAction.flag,
            severity=severity,
            reason=f"Admin action: {reason}",
        )
        return Decision(status=status, action=RuleAction.flag, violations=[violation])
