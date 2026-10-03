from __future__ import annotations

from fastapi.responses import JSONResponse

from control_layer.application.use_cases.outcomes import ToolCallOutcome
from control_layer.domain.models.alert import Alert
from control_layer.domain.models.audit import CallRecord
from control_layer.domain.models.approval import PendingApproval
from control_layer.presentation.api.schemas.alerts import AlertSchema
from control_layer.presentation.api.schemas.approvals import ApprovalDetailResponse
from control_layer.presentation.api.schemas.audit import AuditRow
from control_layer.presentation.api.schemas.feed import FeedRow, FeedUserRef
from control_layer.presentation.api.schemas.tools import (
    PendingApprovalRef,
    ToolCallEscalatedResponse,
    ToolCallResponse,
)


def _user_ref(record: CallRecord) -> FeedUserRef:
    identity = record.identity
    return FeedUserRef(sub=identity.sub, name=identity.name, role=identity.role)


def feed_row(record: CallRecord) -> FeedRow:
    return FeedRow(
        call_id=record.call_id,
        time=record.timestamp,
        user=_user_ref(record),
        kind=record.kind,
        target=record.target,
        status=record.decision.status,
        stage=record.decision.stage,
        rule_id=record.decision.rule_id,
        reason=record.decision.reason,
    )


def audit_row(record: CallRecord) -> AuditRow:
    return AuditRow(
        **feed_row(record).model_dump(),
        tokens=record.tokens.total,
        cost_usd=record.cost_usd,
        proxy_latency_ms=record.latency.proxy_ms,
    )


def alert_schema(alert: Alert) -> AlertSchema:
    return AlertSchema.model_validate(alert.model_dump())


def approval_detail(approval: PendingApproval) -> ApprovalDetailResponse:
    return ApprovalDetailResponse(
        id=approval.id,
        status=approval.status,
        tool=approval.tool_call.qualified_name,
        arguments=approval.tool_call.arguments,
        rule_id=approval.rule_id,
        reason=approval.reason,
        created_at=approval.created_at,
        expires_at=approval.expires_at,
    )


def tool_outcome_response(outcome: ToolCallOutcome) -> JSONResponse:
    if outcome.approval is not None:
        expires = outcome.approval.expires_at
        body = ToolCallEscalatedResponse(
            call_id=outcome.call_id,
            status=outcome.status,
            stage=outcome.stage,
            rule_id=outcome.rule_id,
            reason=outcome.reason,
            approval=PendingApprovalRef(
                id=outcome.approval.id,
                expires_at=expires.isoformat() if expires is not None else None,
            ),
        )
        return JSONResponse(status_code=202, content=body.model_dump(mode="json"))
    assert outcome.result is not None
    ok = ToolCallResponse(
        call_id=outcome.call_id,
        status=outcome.status,
        stage=outcome.stage,
        rule_id=outcome.rule_id,
        reason=outcome.reason,
        items_masked=outcome.items_masked,
        result=outcome.result,
    )
    return JSONResponse(status_code=200, content=ok.model_dump(mode="json"))
