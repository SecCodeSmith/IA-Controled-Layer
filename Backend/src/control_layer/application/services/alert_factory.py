from __future__ import annotations

import secrets

from control_layer.domain.models.alert import Alert, AlertUserRef
from control_layer.domain.models.audit import CallRecord
from control_layer.domain.models.decision import Decision
from control_layer.domain.models.enums import CallStatus, Severity, StageName

_FALLBACK_SEVERITY = Severity.high
_FALLBACK_STAGE = StageName.resource


class AlertFactory:
    def build(self, call_record: CallRecord, decision: Decision) -> Alert | None:
        if decision.status == CallStatus.ALLOWED:
            return None

        primary = decision.primary_violation
        if primary is not None:
            severity = primary.severity
            stage = primary.stage
            rule_id: str | None = primary.rule_id
            owasp = primary.owasp
            reason = primary.reason or call_record.decision.reason or ""
            evidence = primary.evidence
        else:
            severity = _FALLBACK_SEVERITY
            stage = call_record.decision.stage or _FALLBACK_STAGE
            rule_id = call_record.decision.rule_id
            owasp = call_record.decision.owasp
            reason = call_record.decision.reason or ""
            evidence = []

        return Alert(
            id="al_" + secrets.token_hex(6),
            created_at=call_record.timestamp,
            call_id=call_record.call_id,
            user=AlertUserRef(
                sub=call_record.identity.sub,
                name=call_record.identity.name,
                role=call_record.identity.role,
            ),
            status=decision.status,
            stage=stage,
            rule_id=rule_id,
            severity=severity,
            owasp=owasp,
            reason=reason,
            evidence=evidence,
        )
