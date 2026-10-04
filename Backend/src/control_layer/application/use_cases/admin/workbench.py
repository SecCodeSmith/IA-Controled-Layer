from __future__ import annotations

import json
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from control_layer.application.audit.call_record_builder import CallRecordBuilder
from control_layer.application.pipeline.processing_pipeline import ProcessingPipeline
from control_layer.application.services.audit_service import AuditService
from control_layer.application.services.call_id_generator import CallIdGenerator
from control_layer.application.services.risk_service import RiskService
from control_layer.application.services.session_service import SessionService
from control_layer.application.use_cases.admin.workbench_views import (
    JudgeView,
    StageView,
    TraceInput,
    TraceView,
    ViolationView,
)
from control_layer.application.use_cases.issue_token import IssueTokenUseCase
from control_layer.application.use_cases.outcomes import ToolCallOutcome
from control_layer.domain.exceptions import ControlLayerError
from control_layer.domain.models.classifier import (
    CLASSIFIER_TRACE_KEY,
    FORCE_VERIFY_KEY,
    TRAINING_SAMPLE_KEY,
)
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import Decision
from control_layer.domain.models.enums import (
    CallKind,
    CallStatus,
    InterceptionPoint,
    RuleAction,
    StageName,
)
from control_layer.domain.models.provider import ProviderInfo
from control_layer.domain.models.tool import ToolCallRequest
from control_layer.domain.ports.audit_repository import AuditRepository

SESSION_PREFIX = "workbench:"
_PROMPT_PASSES = (InterceptionPoint.prompt,)
_TOOL_PASSES = (InterceptionPoint.tool_call, InterceptionPoint.tool_result)
PROMPT_TARGET = "workbench:prompt"
JUDGE_VERDICT_KEY = "judge_verdict"
_SUMMARY_CHARS = 80

_ACTION_BY_STATUS: dict[CallStatus, RuleAction] = {
    CallStatus.ALLOWED: RuleAction.allow,
    CallStatus.MASKED: RuleAction.mask,
    CallStatus.FLAGGED: RuleAction.flag,
    CallStatus.ESCALATED: RuleAction.require_approval,
    CallStatus.BLOCKED: RuleAction.block,
}


class ProviderDescriber(Protocol):
    def describe(self) -> ProviderInfo: ...


class ToolCallExecutor(Protocol):
    async def execute(
        self, token: str, session_id: str, request: ToolCallRequest
    ) -> ToolCallOutcome: ...


@dataclass(frozen=True)
class _Verdict:
    status: CallStatus
    action: RuleAction
    stage: StageName | None = None
    rule_id: str | None = None
    reason: str | None = None
    stages: list[StageView] = field(default_factory=list)


def _primary_fields(decision: Decision) -> tuple[StageName | None, str | None, str | None]:
    primary = decision.primary_violation
    if primary is not None:
        return primary.stage, primary.rule_id, primary.reason
    structural = next((r for r in decision.stage_results if r.action != RuleAction.allow), None)
    if structural is not None:
        return structural.stage, None, structural.reason
    return None, None, None


def _stage_points(
    decision: Decision, passes: Sequence[InterceptionPoint]
) -> list[InterceptionPoint]:
    points: list[InterceptionPoint] = []
    index = 0
    for position, result in enumerate(decision.stage_results):
        if position > 0 and result.stage is StageName.identity:
            index = min(index + 1, len(passes) - 1)
        points.append(passes[index])
    return points


def _stage_views(decision: Decision, passes: Sequence[InterceptionPoint]) -> list[StageView]:
    points = _stage_points(decision, passes)
    return [
        StageView(
            stage=result.stage,
            point=point,
            action=result.action,
            timing_ms=result.timing_ms,
            cache_hit=result.cache_hit,
            violations=[
                ViolationView(
                    rule_id=violation.rule_id,
                    action=violation.action,
                    confidence=violation.confidence,
                    reason=violation.reason,
                    evidence=list(violation.evidence),
                )
                for violation in result.violations
            ],
        )
        for result, point in zip(decision.stage_results, points, strict=True)
    ]


def _verdict_from_decision(decision: Decision, passes: Sequence[InterceptionPoint]) -> _Verdict:
    stage, rule_id, reason = _primary_fields(decision)
    return _Verdict(
        status=decision.status,
        action=decision.action,
        stage=stage,
        rule_id=rule_id,
        reason=reason,
        stages=_stage_views(decision, passes),
    )


def _verdict_from_outcome(outcome: ToolCallOutcome) -> _Verdict:
    if outcome.decision is not None:
        return _verdict_from_decision(outcome.decision, _TOOL_PASSES)
    return _Verdict(
        status=outcome.status,
        action=_ACTION_BY_STATUS[outcome.status],
        stage=outcome.stage,
        rule_id=outcome.rule_id,
        reason=outcome.reason,
    )


def _verdict_from_error(error: ControlLayerError) -> _Verdict:
    decision = getattr(error, "decision", None)
    if decision is not None:
        return _verdict_from_decision(decision, _TOOL_PASSES)
    violation = getattr(error, "violation", None)
    return _Verdict(
        status=getattr(error, "status", CallStatus.BLOCKED),
        action=RuleAction.block,
        stage=violation.stage if violation is not None else None,
        rule_id=violation.rule_id if violation is not None else None,
        reason=violation.reason if violation is not None else str(error),
    )


def _parse_payload(text: str | None) -> Any:
    if text is None:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return text


class WorkbenchTraceUseCase:
    def __init__(
        self,
        pipeline: ProcessingPipeline,
        issue_token: IssueTokenUseCase,
        session_service: SessionService,
        audit_service: AuditService,
        risk_service: RiskService,
        call_ids: CallIdGenerator,
        tool_call_use_case: ToolCallExecutor,
        audit_repository: AuditRepository,
        model_provider: ProviderDescriber,
    ) -> None:
        self._pipeline = pipeline
        self._issue_token = issue_token
        self._session_service = session_service
        self._audit_service = audit_service
        self._risk_service = risk_service
        self._call_ids = call_ids
        self._tool_call = tool_call_use_case
        self._audit_repository = audit_repository
        self._model_provider = model_provider
        self._record_builder = CallRecordBuilder()

    async def execute(self, request: TraceInput) -> TraceView:
        token = (await self._issue_token.execute(request.actor)).access_token
        session_id = f"{SESSION_PREFIX}{request.actor}"
        if request.kind == "prompt":
            return await self._trace_prompt(request, token, session_id)
        return await self._trace_tool_call(request, token, session_id)

    async def _trace_prompt(self, request: TraceInput, token: str, session_id: str) -> TraceView:
        start = time.perf_counter()
        text = request.text or ""
        call_id = await self._call_ids.next()
        ctx = ProcessingContext(
            identity=None,
            point=InterceptionPoint.prompt,
            text=text,
            session_id=session_id,
            call_id=call_id,
            metadata={
                "token": token,
                "session_state": await self._session_service.load(session_id),
                "model": self._model_provider.describe().model,
                FORCE_VERIFY_KEY: request.force_verify,
            },
        )
        decision = await self._pipeline.run(ctx)
        await self._audit_prompt(ctx, decision, time.perf_counter() - start)
        verdict = _verdict_from_decision(decision, _PROMPT_PASSES)
        return self._response(
            call_id,
            "prompt",
            verdict,
            masked_text=ctx.masked_text,
            classifier_trace=ctx.metadata.get(CLASSIFIER_TRACE_KEY),
            judge=self._judge_view(ctx.metadata.get(JUDGE_VERDICT_KEY)),
            training_sample_id=ctx.metadata.get(TRAINING_SAMPLE_KEY),
        )

    async def _audit_prompt(
        self, ctx: ProcessingContext, decision: Decision, elapsed_s: float
    ) -> None:
        identity = ctx.identity
        assert identity is not None
        stage, rule_id, reason = _primary_fields(decision)
        primary = decision.primary_violation
        record = self._record_builder.build(
            call_id=ctx.call_id,
            identity=identity,
            kind=CallKind.workbench,
            target=PROMPT_TARGET,
            status=decision.status,
            provider=self._model_provider.describe(),
            stage=stage,
            rule_id=rule_id,
            reason=reason,
            owasp=primary.owasp if primary is not None else [],
            request_summary=f"workbench: {ctx.text[:_SUMMARY_CHARS]}",
            request_payload={"actor": identity.sub},
            delivered_response=ctx.masked_text,
            proxy_latency_ms=elapsed_s * 1000,
            stage_timings=decision.stage_timings_ms,
        )
        await self._risk_service.record(identity, decision)
        await self._audit_service.record(record, decision)

    async def _trace_tool_call(self, request: TraceInput, token: str, session_id: str) -> TraceView:
        spec = request.tool_call
        assert spec is not None
        call = ToolCallRequest(
            server=spec.server, tool=spec.tool, arguments=spec.arguments, session_id=session_id
        )
        try:
            outcome = await self._tool_call.execute(token, session_id, call)
        except ControlLayerError as error:
            if error.call_id is None:
                raise
            return await self._tool_response(error.call_id, _verdict_from_error(error))
        return await self._tool_response(outcome.call_id, _verdict_from_outcome(outcome))

    async def _tool_response(self, call_id: str, verdict: _Verdict) -> TraceView:
        record = await self._audit_repository.get(call_id)
        raw, delivered = (
            (record.response.raw, record.response.delivered) if record is not None else (None, None)
        )
        return self._response(
            call_id,
            "tool_call",
            verdict,
            raw_result=_parse_payload(raw),
            delivered_result=_parse_payload(delivered),
        )

    @staticmethod
    def _judge_view(payload: dict | None) -> JudgeView | None:
        return JudgeView.model_validate(payload) if payload else None

    @staticmethod
    def _response(call_id: str, kind: str, verdict: _Verdict, **extra: Any) -> TraceView:
        return TraceView(
            call_id=call_id,
            kind=kind,
            status=verdict.status,
            action=verdict.action,
            stage=verdict.stage,
            rule_id=verdict.rule_id,
            reason=verdict.reason,
            stages=verdict.stages,
            **extra,
        )
