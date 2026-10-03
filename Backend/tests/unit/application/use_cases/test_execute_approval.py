from __future__ import annotations

from datetime import UTC, datetime

import pytest

from control_layer.application.use_cases.execute_approval import ExecuteApprovalUseCase
from control_layer.application.use_cases.outcomes import ToolCallOutcome
from control_layer.domain.exceptions import ApprovalNotFoundError
from control_layer.domain.models.approval import PendingApproval
from control_layer.domain.models.enums import ApprovalStatus, CallStatus, Role
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.provider import ProviderInfo
from control_layer.domain.models.tool import ToolCallRequest


def _identity() -> Identity:
    return Identity(
        sub="anna.kowalska",
        name="Anna Kowalska",
        role=Role.developer,
        location="Krakow, PL",
        region="PL",
        agent_id="agent-anna",
    )


class _IdentityService:
    async def resolve(self, token, session_id):  # noqa: ANN001, ANN201
        return _identity()


class _ApprovalService:
    def __init__(self) -> None:
        self.approval = PendingApproval(
            id="ap_1",
            identity=_identity(),
            tool_call=ToolCallRequest(server="github", tool="delete_branch", arguments={"b": "x"}),
            created_at=datetime(2026, 10, 3, tzinfo=UTC),
            rule_id="destructive_requires_approval",
            status=ApprovalStatus.pending,
        )
        self.marks: list[ApprovalStatus] = []

    async def get_for(self, identity, approval_id):  # noqa: ANN001, ANN201
        if self.approval.status != ApprovalStatus.pending:
            raise ApprovalNotFoundError(approval_id)
        return self.approval

    async def mark(self, approval_id, status) -> None:  # noqa: ANN001
        self.marks.append(status)
        self.approval = self.approval.model_copy(update={"status": status})


class _HandleToolCall:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def execute(self, token, session_id, request, *, approved=False):  # noqa: ANN001, ANN201
        self.calls.append((session_id, request, approved))
        return ToolCallOutcome(call_id="c_1", status=CallStatus.ALLOWED)


class _AuditService:
    def __init__(self) -> None:
        self.records: list = []

    async def record(self, call, decision):  # noqa: ANN001, ANN201
        self.records.append((call, decision))


class _CallIds:
    async def next(self) -> str:
        return "c_9"


class _Provider:
    def describe(self) -> ProviderInfo:
        return ProviderInfo(name="mock", model="mock")


def _use_case():  # noqa: ANN202
    approvals, handler, audit = _ApprovalService(), _HandleToolCall(), _AuditService()
    use_case = ExecuteApprovalUseCase(
        approvals, _IdentityService(), handler, audit, _CallIds(), _Provider()
    )
    return use_case, approvals, handler, audit


async def test_approve_executes_once_with_approved_flag_and_marks_executed() -> None:
    use_case, approvals, handler, _ = _use_case()
    outcome = await use_case.approve("t", "ap_1")
    assert outcome.status == CallStatus.ALLOWED
    assert len(handler.calls) == 1 and handler.calls[0][2] is True
    assert approvals.marks == [ApprovalStatus.approved, ApprovalStatus.executed]


async def test_second_approve_raises_not_found() -> None:
    use_case, _, handler, _ = _use_case()
    await use_case.approve("t", "ap_1")
    with pytest.raises(ApprovalNotFoundError):
        await use_case.approve("t", "ap_1")
    assert len(handler.calls) == 1


async def test_reject_marks_rejected_and_audits_blocked() -> None:
    use_case, approvals, handler, audit = _use_case()
    result = await use_case.reject("t", "ap_1")
    assert result.status == ApprovalStatus.rejected
    assert approvals.marks == [ApprovalStatus.rejected]
    assert handler.calls == []
    call = audit.records[0][0]
    assert call.decision.status == CallStatus.BLOCKED
    assert call.decision.reason == "Rejected by user"
