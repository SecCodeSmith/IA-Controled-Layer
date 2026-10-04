from __future__ import annotations

import json
import re
import time

from control_layer.application.audit.call_record_builder import CallRecordBuilder
from control_layer.application.auth.identity_service import IdentityService
from control_layer.application.dlp.session_vault import SessionVault
from control_layer.application.pipeline.processing_pipeline import ProcessingPipeline
from control_layer.application.services.approval_service import ApprovalService
from control_layer.application.services.audit_service import AuditService
from control_layer.application.services.call_id_generator import CallIdGenerator
from control_layer.application.services.circuit_breaker_service import CircuitBreakerService
from control_layer.application.services.risk_service import RiskService
from control_layer.application.services.session_service import SessionService
from control_layer.application.services.tool_catalog import ToolCatalog
from control_layer.application.use_cases.outcomes import ToolCallOutcome
from control_layer.domain.exceptions import (
    BudgetExceededError,
    ControlLayerError,
    PolicyViolationError,
    QuarantinedError,
    RateLimitedError,
)
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import Decision, merge_action, status_for
from control_layer.domain.models.enums import (
    CallKind,
    CallStatus,
    InterceptionPoint,
    RuleAction,
    StageName,
)
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.tool import ToolCallRequest, ToolCallResult
from control_layer.domain.policy.vault import restorable_kinds_for_tool
from control_layer.domain.ports.mcp_gateway import McpGateway
from control_layer.domain.ports.model_provider import ModelProvider
from control_layer.domain.ports.policy_repository import PolicyRepository

_BLOCKING_ACTIONS = (RuleAction.block, RuleAction.quarantine)
_PLACEHOLDER_RE = re.compile(r"\[[A-Z0-9_]+_\d+\]")


def _count_placeholders(text: str | None) -> int:
    return len(_PLACEHOLDER_RE.findall(text)) if text else 0


def _combine(decision1: Decision, decision2: Decision | None) -> Decision:
    if decision2 is None:
        return decision1
    violations = list(decision1.violations) + list(decision2.violations)
    action = merge_action([decision1.action, decision2.action])
    return Decision(
        status=status_for(action),
        action=action,
        violations=violations,
        stage_results=list(decision1.stage_results) + list(decision2.stage_results),
        stage_timings_ms={**decision1.stage_timings_ms, **decision2.stage_timings_ms},
    )


def _outcome_fields(
    decision: Decision,
) -> tuple[StageName | None, str | None, str | None, list[str]]:
    primary = decision.primary_violation
    if primary is not None:
        return primary.stage, primary.rule_id, primary.reason, primary.owasp
    structural = next((r for r in decision.stage_results if r.action != RuleAction.allow), None)
    if structural is not None:
        return structural.stage, None, structural.reason, []
    return None, None, None, []


def _had_policy_stage_violation(decision: Decision) -> bool:
    return any(v.stage == StageName.policy for v in decision.violations)


class HandleToolCallUseCase:
    def __init__(
        self,
        pipeline: ProcessingPipeline,
        tool_catalog: ToolCatalog,
        mcp_gateway: McpGateway,
        approval_service: ApprovalService,
        session_service: SessionService,
        audit_service: AuditService,
        circuit_breaker: CircuitBreakerService,
        risk_service: RiskService,
        call_ids: CallIdGenerator,
        policy_repository: PolicyRepository,
        model_provider: ModelProvider,
        vault: SessionVault | None = None,
        identity_service: IdentityService | None = None,
    ) -> None:
        self._pipeline = pipeline
        self._tool_catalog = tool_catalog
        self._mcp_gateway = mcp_gateway
        self._approval_service = approval_service
        self._session_service = session_service
        self._audit_service = audit_service
        self._circuit_breaker = circuit_breaker
        self._risk_service = risk_service
        self._call_ids = call_ids
        self._policy_repository = policy_repository
        self._model_provider = model_provider
        self._vault = vault
        self._identity_service = identity_service
        self._record_builder = CallRecordBuilder()

    async def execute(
        self, token: str, session_id: str, request: ToolCallRequest, *, approved: bool = False
    ) -> ToolCallOutcome:
        start = time.perf_counter()
        call_id = await self._call_ids.next()
        descriptor = await self._tool_catalog.descriptor(request.server, request.tool)
        session_state = await self._session_service.load(session_id)

        received = request
        request, items_restored = await self._restore_arguments(token, session_id, received)

        canonical_text = json.dumps(
            {"server": request.server, "tool": request.tool, "arguments": request.arguments},
            sort_keys=True,
            separators=(",", ":"),
        )

        ctx1 = ProcessingContext(
            identity=None,
            point=InterceptionPoint.tool_call,
            text=canonical_text,
            tool_call=request,
            session_id=session_id,
            call_id=call_id,
            metadata={
                "token": token,
                "tool_descriptor": descriptor,
                "session_state": session_state,
                "approved": approved,
            },
        )
        decision1 = await self._pipeline.run(ctx1)
        identity = ctx1.identity
        assert identity is not None

        if decision1.action == RuleAction.require_approval:
            primary = decision1.primary_violation
            rule_id = primary.rule_id if primary else "unknown"
            reason = (primary.reason if primary else None) or "Approval required"
            stage = primary.stage if primary else StageName.authorization
            approval = await self._approval_service.create(identity, received, rule_id, reason)

            proxy_latency_ms = (time.perf_counter() - start) * 1000
            await self._risk_service.record(identity, decision1)
            await self._audit(
                identity=identity,
                call_id=call_id,
                decision=decision1,
                request=received,
                proxy_latency_ms=proxy_latency_ms,
            )
            return ToolCallOutcome(
                call_id=call_id,
                status=CallStatus.ESCALATED,
                stage=stage,
                rule_id=rule_id,
                reason=reason,
                items_masked=0,
                items_restored=0,
                result=None,
                approval=approval,
            )

        if decision1.action in _BLOCKING_ACTIONS:
            proxy_latency_ms = (time.perf_counter() - start) * 1000
            await self._circuit_breaker.record_block(identity, call_id)
            await self._risk_service.record(identity, decision1)
            await self._audit(
                identity=identity,
                call_id=call_id,
                decision=decision1,
                request=received,
                proxy_latency_ms=proxy_latency_ms,
            )
            raise self._mapped_error(decision1, call_id)

        tool_result = await self._mcp_gateway.call_tool(request)

        ctx2 = ProcessingContext(
            identity=identity,
            point=InterceptionPoint.tool_result,
            text=tool_result.content_text,
            tool_call=request,
            session_id=session_id,
            call_id=call_id,
            metadata={
                "token": token,
                "tool_descriptor": descriptor,
                "session_state": ctx1.metadata.get("session_state"),
                "injection_detected": _had_policy_stage_violation(decision1),
            },
        )
        decision2 = await self._pipeline.run(ctx2)
        combined = _combine(decision1, decision2)

        if decision2.action in _BLOCKING_ACTIONS:
            proxy_latency_ms = (time.perf_counter() - start) * 1000
            await self._circuit_breaker.record_block(identity, call_id)
            await self._risk_service.record(identity, combined)
            await self._audit(
                identity=identity,
                call_id=call_id,
                decision=combined,
                request=received,
                proxy_latency_ms=proxy_latency_ms,
                raw_response=tool_result.content_text,
            )
            raise self._mapped_error(combined, call_id)

        delivered_text = (
            ctx2.masked_text if ctx2.masked_text is not None else tool_result.content_text
        )
        items_masked = _count_placeholders(ctx1.masked_text) + _count_placeholders(ctx2.masked_text)

        await self._risk_service.record(identity, combined)
        proxy_latency_ms = (time.perf_counter() - start) * 1000
        stage, rule_id, reason, owasp = _outcome_fields(combined)

        await self._audit(
            identity=identity,
            call_id=call_id,
            decision=combined,
            request=received,
            proxy_latency_ms=proxy_latency_ms,
            raw_response=tool_result.content_text,
            delivered_response=delivered_text,
            items_masked=items_masked,
            items_restored=items_restored,
        )

        result = ToolCallResult(
            content_text=delivered_text,
            structured_content=tool_result.structured_content,
            is_error=tool_result.is_error,
        )
        return ToolCallOutcome(
            call_id=call_id,
            status=combined.status,
            stage=stage,
            rule_id=rule_id,
            reason=reason,
            items_masked=items_masked,
            items_restored=items_restored,
            result=result,
            approval=None,
        )

    async def _restore_arguments(
        self, token: str, session_id: str, request: ToolCallRequest
    ) -> tuple[ToolCallRequest, int]:
        if self._vault is None or self._identity_service is None or not request.arguments:
            return request, 0
        try:
            caller = await self._identity_service.resolve(token, session_id)
        except ControlLayerError:
            return request, 0
        policy = await self._policy_repository.current()
        allowed = restorable_kinds_for_tool(policy, request.qualified_name)
        if not allowed:
            return request, 0
        arguments, count = await self._vault.restore_value(
            session_id, request.arguments, allowed, sub=caller.sub
        )
        if count == 0:
            return request, 0
        return request.model_copy(update={"arguments": arguments}), count

    async def _audit(
        self,
        *,
        identity: Identity,
        call_id: str,
        decision: Decision,
        request: ToolCallRequest,
        proxy_latency_ms: float,
        raw_response: str | None = None,
        delivered_response: str | None = None,
        items_masked: int = 0,
        items_restored: int = 0,
    ) -> None:
        stage, rule_id, reason, owasp = _outcome_fields(decision)
        call_record = self._record_builder.build(
            call_id=call_id,
            identity=identity,
            kind=CallKind.tool_call,
            target=request.qualified_name,
            mcp_server=request.server,
            status=decision.status,
            provider=self._model_provider.describe(),
            stage=stage,
            rule_id=rule_id,
            reason=reason,
            owasp=owasp,
            request_summary=f"tool: {request.qualified_name}",
            request_payload=request.arguments,
            raw_response=raw_response,
            delivered_response=delivered_response,
            items_masked=items_masked,
            items_restored=items_restored,
            proxy_latency_ms=proxy_latency_ms,
            stage_timings=decision.stage_timings_ms,
        )
        await self._audit_service.record(call_record, decision)

    @staticmethod
    def _mapped_error(decision: Decision, call_id: str) -> ControlLayerError:
        resource_block = next(
            (
                r
                for r in decision.stage_results
                if r.stage == StageName.resource and r.action == RuleAction.block
            ),
            None,
        )
        primary = decision.primary_violation
        if resource_block is not None:
            error: ControlLayerError = BudgetExceededError(
                resource_block.reason or "Budget exceeded"
            )
        elif decision.action == RuleAction.quarantine:
            fallback = primary.reason if primary is not None else None
            error = QuarantinedError(fallback or "User is quarantined")
        elif primary is not None and primary.rule_id == "rate_limit":
            error = RateLimitedError(primary.reason or "Rate limit exceeded")
        elif primary is not None:
            error = PolicyViolationError(primary, decision.status)
        else:
            error = QuarantinedError("Request blocked")
        error.call_id = call_id
        return error
