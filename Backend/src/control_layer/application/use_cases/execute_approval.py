from __future__ import annotations

from control_layer.application.audit.call_record_builder import CallRecordBuilder
from control_layer.application.auth.identity_service import IdentityService
from control_layer.application.services.approval_service import ApprovalService
from control_layer.application.services.audit_service import AuditService
from control_layer.application.services.call_id_generator import CallIdGenerator
from control_layer.application.use_cases.handle_tool_call import HandleToolCallUseCase
from control_layer.application.use_cases.outcomes import ToolCallOutcome
from control_layer.domain.models.approval import PendingApproval
from control_layer.domain.models.decision import Decision
from control_layer.domain.models.enums import (
    ApprovalStatus,
    CallKind,
    CallStatus,
    RuleAction,
    StageName,
)
from control_layer.domain.ports.model_provider import ModelProvider

_REJECTED_REASON = "Rejected by user"


class ExecuteApprovalUseCase:
    def __init__(
        self,
        approval_service: ApprovalService,
        identity_service: IdentityService,
        handle_tool_call: HandleToolCallUseCase,
        audit_service: AuditService,
        call_ids: CallIdGenerator,
        model_provider: ModelProvider,
    ) -> None:
        self._approval_service = approval_service
        self._identity_service = identity_service
        self._handle_tool_call = handle_tool_call
        self._audit_service = audit_service
        self._call_ids = call_ids
        self._model_provider = model_provider
        self._record_builder = CallRecordBuilder()

    async def approve(self, token: str, approval_id: str) -> ToolCallOutcome:
        identity = await self._identity_service.resolve(token, session_id="")
        approval = await self._approval_service.get_for(identity, approval_id)

        await self._approval_service.mark(approval_id, ApprovalStatus.approved)
        session_id = approval.tool_call.session_id or identity.sub
        outcome = await self._handle_tool_call.execute(
            token, session_id, approval.tool_call, approved=True
        )
        await self._approval_service.mark(approval_id, ApprovalStatus.executed)
        return outcome

    async def reject(self, token: str, approval_id: str) -> PendingApproval:
        identity = await self._identity_service.resolve(token, session_id="")
        approval = await self._approval_service.get_for(identity, approval_id)
        await self._approval_service.mark(approval_id, ApprovalStatus.rejected)

        call_id = await self._call_ids.next()
        call_record = self._record_builder.build(
            call_id=call_id,
            identity=identity,
            kind=CallKind.tool_call,
            target=approval.tool_call.qualified_name,
            mcp_server=approval.tool_call.server,
            status=CallStatus.BLOCKED,
            provider=self._model_provider.describe(),
            stage=StageName.authorization,
            rule_id=approval.rule_id,
            reason=_REJECTED_REASON,
            request_summary=f"tool: {approval.tool_call.qualified_name}",
            request_payload=approval.tool_call.arguments,
        )
        decision = Decision(status=CallStatus.BLOCKED, action=RuleAction.block, violations=[])
        await self._audit_service.record(call_record, decision)

        return approval.model_copy(update={"status": ApprovalStatus.rejected})
