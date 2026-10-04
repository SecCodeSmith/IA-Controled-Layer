from __future__ import annotations

import json

import pytest

from control_layer.application.use_cases.admin.workbench import WorkbenchTraceUseCase
from control_layer.application.use_cases.outcomes import TokenIssued, ToolCallOutcome
from control_layer.domain.exceptions import (
    ControlLayerError,
    IdentityRejectedError,
    PolicyViolationError,
    UnknownToolError,
)
from control_layer.domain.models.audit import (
    CallDecisionInfo,
    CallLatency,
    CallRecord,
    CallRequestInfo,
    CallResponseInfo,
    TokensInfo,
)
from control_layer.domain.models.classifier import (
    CLASSIFIER_TRACE_KEY,
    FORCE_VERIFY_KEY,
    TRAINING_SAMPLE_KEY,
    ClassifierTrace,
)
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import Decision, StageResult, Violation
from control_layer.domain.models.enums import (
    CallKind,
    CallStatus,
    InterceptionPoint,
    Role,
    RuleAction,
    Severity,
    StageName,
)
from control_layer.domain.models.identity import Identity, TokenClaims
from control_layer.domain.models.provider import ProviderInfo
from control_layer.domain.models.session import SessionState
from control_layer.domain.models.tool import ToolCallResult
from control_layer.presentation.api.schemas.workbench import ToolCallSpec, TraceRequest

ANNA = Identity(
    sub="anna.kowalska",
    name="Anna Kowalska",
    role=Role.developer,
    location="PL",
    region="PL",
    agent_id="agent-anna",
)


def _stage(stage: StageName, action: RuleAction = RuleAction.allow, violations=()) -> StageResult:
    return StageResult(
        stage=stage, action=action, violations=list(violations), timing_ms=1.5, cache_hit=False
    )


def _violation(rule_id: str, action: RuleAction, stage: StageName) -> Violation:
    return Violation(
        stage=stage,
        rule_id=rule_id,
        action=action,
        severity=Severity.high,
        owasp=["LLM01"],
        evidence=["ignore all previous"],
        confidence=0.9,
        reason=f"{rule_id} matched",
    )


def _decision(
    action: RuleAction = RuleAction.allow,
    violations=(),
    stages=None,
    status: CallStatus = CallStatus.ALLOWED,
    masked_text: str | None = None,
) -> Decision:
    stages = stages or [_stage(name) for name in StageName.ordered()]
    return Decision(
        status=status,
        action=action,
        violations=list(violations),
        masked_text=masked_text,
        stage_results=stages,
        stage_timings_ms={s.stage.value: s.timing_ms for s in stages},
    )


def _blocked_decision() -> Decision:
    violation = _violation("prompt_injection_signatures", RuleAction.block, StageName.policy)
    stages = [
        _stage(StageName.identity),
        _stage(StageName.authorization),
        _stage(StageName.dlp),
        _stage(StageName.policy, RuleAction.block, [violation]),
        _stage(StageName.audit),
    ]
    return _decision(RuleAction.block, [violation], stages, CallStatus.BLOCKED)


class ScriptedPipeline:
    def __init__(self, decision: Decision, metadata_updates: dict | None = None) -> None:
        self.decision = decision
        self.metadata_updates = metadata_updates or {}
        self.contexts: list[ProcessingContext] = []

    async def run(self, ctx: ProcessingContext) -> Decision:
        self.contexts.append(ctx)
        ctx.identity = ANNA
        ctx.metadata.update(self.metadata_updates)
        ctx.masked_text = self.decision.masked_text
        return self.decision


class FakeIssueToken:
    def __init__(self) -> None:
        self.subjects: list[str] = []

    async def execute(self, sub: str) -> TokenIssued:
        self.subjects.append(sub)
        if sub == "ghost":
            raise IdentityRejectedError(f"unknown user: {sub}")
        claims = TokenClaims(
            sub=sub,
            name=sub,
            role=Role.developer,
            location="PL",
            region="PL",
            agent_id="a",
            iat=0,
            exp=1,
        )
        return TokenIssued(access_token=f"token-{sub}", expires_in=1, claims=claims)


class FakeSessionService:
    async def load(self, session_id: str) -> SessionState:
        return SessionState(session_id=session_id)


class RecordingAuditService:
    def __init__(self) -> None:
        self.records: list[tuple[CallRecord, Decision]] = []

    async def record(self, call: CallRecord, decision: Decision) -> None:
        self.records.append((call, decision))


class RecordingRiskService:
    def __init__(self) -> None:
        self.recorded: list[tuple[Identity, Decision]] = []

    async def record(self, identity: Identity, decision: Decision) -> None:
        self.recorded.append((identity, decision))


class FakeCallIds:
    async def next(self) -> str:
        return "c_000042"


class FakeProvider:
    def describe(self) -> ProviderInfo:
        return ProviderInfo(name="mock", model="mock")


class FakeAuditRepository:
    def __init__(self, records: dict[str, CallRecord] | None = None) -> None:
        self.records = records or {}

    async def get(self, call_id: str) -> CallRecord | None:
        return self.records.get(call_id)


class FakeToolCall:
    def __init__(self, outcome: ToolCallOutcome | None = None, error=None) -> None:
        self.outcome = outcome
        self.error = error
        self.calls: list[tuple[str, str, object]] = []

    async def execute(self, token, session_id, request):
        self.calls.append((token, session_id, request))
        if self.error is not None:
            raise self.error
        return self.outcome


def _tool_record(call_id: str, raw: str | None, delivered: str | None) -> CallRecord:
    return CallRecord(
        call_id=call_id,
        timestamp="2026-10-04T10:00:00Z",
        identity=ANNA,
        kind=CallKind.tool_call,
        target="github.read_file",
        decision=CallDecisionInfo(status=CallStatus.ALLOWED),
        request=CallRequestInfo(summary="tool"),
        response=CallResponseInfo(raw=raw, delivered=delivered),
        tokens=TokensInfo(),
        latency=CallLatency(proxy_ms=1.0, upstream_ms=0.0),
        provider=ProviderInfo(name="mock", model="mock"),
    )


class Harness:
    def __init__(
        self,
        decision: Decision | None = None,
        metadata_updates: dict | None = None,
        tool_call: FakeToolCall | None = None,
        audit_repository: FakeAuditRepository | None = None,
    ) -> None:
        self.pipeline = ScriptedPipeline(decision or _decision(), metadata_updates)
        self.issue_token = FakeIssueToken()
        self.audit_service = RecordingAuditService()
        self.risk_service = RecordingRiskService()
        self.tool_call = tool_call or FakeToolCall()
        self.use_case = WorkbenchTraceUseCase(
            pipeline=self.pipeline,
            issue_token=self.issue_token,
            session_service=FakeSessionService(),
            audit_service=self.audit_service,
            risk_service=self.risk_service,
            call_ids=FakeCallIds(),
            tool_call_use_case=self.tool_call,
            audit_repository=audit_repository or FakeAuditRepository(),
            model_provider=FakeProvider(),
        )


def _prompt(text: str = "hello", **extra) -> TraceRequest:
    return TraceRequest(actor="anna.kowalska", kind="prompt", text=text, **extra)


def _tool_request() -> TraceRequest:
    return TraceRequest(
        actor="anna.kowalska",
        kind="tool_call",
        tool_call=ToolCallSpec(server="github", tool="read_file", arguments={"path": "src/app.py"}),
    )


@pytest.mark.asyncio
async def test_prompt_trace_mints_token_for_actor_and_builds_workbench_context() -> None:
    harness = Harness()

    await harness.use_case.execute(_prompt("hello world", force_verify=True))

    assert harness.issue_token.subjects == ["anna.kowalska"]
    ctx = harness.pipeline.contexts[0]
    assert ctx.point is InterceptionPoint.prompt
    assert ctx.text == "hello world"
    assert ctx.session_id == "workbench:anna.kowalska"
    assert ctx.call_id == "c_000042"
    assert ctx.metadata["token"] == "token-anna.kowalska"
    assert ctx.metadata["model"] == "mock"
    assert ctx.metadata[FORCE_VERIFY_KEY] is True
    assert ctx.metadata["session_state"].session_id == "workbench:anna.kowalska"


@pytest.mark.asyncio
async def test_prompt_trace_defaults_force_verify_to_false() -> None:
    harness = Harness()

    await harness.use_case.execute(_prompt())

    assert harness.pipeline.contexts[0].metadata[FORCE_VERIFY_KEY] is False


@pytest.mark.asyncio
async def test_prompt_trace_records_one_workbench_call_record() -> None:
    harness = Harness(_decision())

    await harness.use_case.execute(_prompt("x" * 200))

    assert len(harness.audit_service.records) == 1
    record, decision = harness.audit_service.records[0]
    assert record.kind is CallKind.workbench
    assert record.target == "workbench:prompt"
    assert record.request.summary == f"workbench: {'x' * 80}"
    assert record.call_id == "c_000042"
    assert record.identity == ANNA
    assert record.decision.status is CallStatus.ALLOWED
    assert record.latency.stages == decision.stage_timings_ms
    assert harness.risk_service.recorded == [(ANNA, decision)]


@pytest.mark.asyncio
async def test_prompt_trace_audits_delivered_response_as_masked_text() -> None:
    harness = Harness(_decision(masked_text="reach me at [EMAIL_1]"))

    response = await harness.use_case.execute(_prompt("reach me at a@b.pl"))

    record, _ = harness.audit_service.records[0]
    assert record.response.delivered == "reach me at [EMAIL_1]"
    assert response.masked_text == "reach me at [EMAIL_1]"


@pytest.mark.asyncio
async def test_prompt_trace_returns_stages_in_pipeline_order_with_violations() -> None:
    harness = Harness(_blocked_decision())

    response = await harness.use_case.execute(_prompt())

    assert [s.stage for s in response.stages] == [
        StageName.identity,
        StageName.authorization,
        StageName.dlp,
        StageName.policy,
        StageName.audit,
    ]
    policy_stage = response.stages[3]
    assert policy_stage.action is RuleAction.block
    assert policy_stage.timing_ms == 1.5
    assert policy_stage.cache_hit is False
    [violation] = policy_stage.violations
    assert violation.rule_id == "prompt_injection_signatures"
    assert violation.action is RuleAction.block
    assert violation.confidence == 0.9
    assert violation.reason == "prompt_injection_signatures matched"
    assert violation.evidence == ["ignore all previous"]


@pytest.mark.asyncio
async def test_blocked_prompt_returns_status_without_raising() -> None:
    harness = Harness(_blocked_decision())

    response = await harness.use_case.execute(_prompt())

    assert response.kind == "prompt"
    assert response.call_id == "c_000042"
    assert response.status is CallStatus.BLOCKED
    assert response.action is RuleAction.block
    assert response.stage is StageName.policy
    assert response.rule_id == "prompt_injection_signatures"
    assert response.reason == "prompt_injection_signatures matched"
    record, _ = harness.audit_service.records[0]
    assert record.decision.status is CallStatus.BLOCKED
    assert record.decision.rule_id == "prompt_injection_signatures"
    assert record.decision.owasp == ["LLM01"]


@pytest.mark.asyncio
async def test_structural_block_without_violation_reports_stage_and_reason() -> None:
    stages = [
        _stage(StageName.identity),
        StageResult(
            stage=StageName.resource,
            action=RuleAction.block,
            timing_ms=0.5,
            reason="Budget exceeded",
        ),
        _stage(StageName.audit),
    ]
    harness = Harness(_decision(RuleAction.block, stages=stages, status=CallStatus.BLOCKED))

    response = await harness.use_case.execute(_prompt())

    assert response.stage is StageName.resource
    assert response.rule_id is None
    assert response.reason == "Budget exceeded"


@pytest.mark.asyncio
async def test_clean_prompt_reports_allowed_without_primary_fields() -> None:
    harness = Harness(_decision())

    response = await harness.use_case.execute(_prompt())

    assert response.status is CallStatus.ALLOWED
    assert response.action is RuleAction.allow
    assert response.stage is None
    assert response.rule_id is None
    assert len(response.stages) == 7
    assert response.classifier_trace is None
    assert response.judge is None
    assert response.training_sample_id is None


@pytest.mark.asyncio
async def test_prompt_trace_maps_classifier_trace_judge_and_sample_from_metadata() -> None:
    trace = ClassifierTrace(rule_id="prompt_injection_tree", probability=0.62, band="escalate")
    harness = Harness(
        _decision(),
        {
            CLASSIFIER_TRACE_KEY: trace,
            "judge_verdict": {"verdict": "block", "confidence": 0.93, "reason": "exfiltration"},
            TRAINING_SAMPLE_KEY: "ts_001",
        },
    )

    response = await harness.use_case.execute(_prompt())

    assert response.classifier_trace == trace
    assert response.judge is not None
    assert response.judge.verdict == "block"
    assert response.judge.confidence == 0.93
    assert response.judge.reason == "exfiltration"
    assert response.training_sample_id == "ts_001"


@pytest.mark.asyncio
async def test_unknown_actor_propagates_identity_rejection_before_any_side_effect() -> None:
    harness = Harness()
    request = TraceRequest(actor="ghost", kind="prompt", text="hi")

    with pytest.raises(IdentityRejectedError):
        await harness.use_case.execute(request)

    assert harness.pipeline.contexts == []
    assert harness.audit_service.records == []


@pytest.mark.asyncio
async def test_tool_trace_delegates_with_workbench_session_and_maps_outcome_decision() -> None:
    outcome = ToolCallOutcome(
        call_id="c_000007",
        status=CallStatus.ALLOWED,
        result=ToolCallResult(content_text="print('hi')"),
        decision=_decision(),
    )
    repository = FakeAuditRepository(
        {"c_000007": _tool_record("c_000007", '{"content": "raw"}', "delivered text")}
    )
    harness = Harness(tool_call=FakeToolCall(outcome), audit_repository=repository)

    response = await harness.use_case.execute(_tool_request())

    token, session_id, call = harness.tool_call.calls[0]
    assert token == "token-anna.kowalska"
    assert session_id == "workbench:anna.kowalska"
    assert (call.server, call.tool, call.arguments) == (
        "github",
        "read_file",
        {"path": "src/app.py"},
    )
    assert call.session_id == "workbench:anna.kowalska"
    assert harness.pipeline.contexts == []
    assert harness.audit_service.records == []
    assert response.kind == "tool_call"
    assert response.call_id == "c_000007"
    assert response.status is CallStatus.ALLOWED
    assert response.action is RuleAction.allow
    assert len(response.stages) == 7
    assert response.raw_result == {"content": "raw"}
    assert response.delivered_result == "delivered text"


@pytest.mark.asyncio
async def test_tool_trace_parses_json_results_and_keeps_plain_text() -> None:
    outcome = ToolCallOutcome(
        call_id="c_000007", status=CallStatus.MASKED, decision=_decision(RuleAction.mask)
    )
    repository = FakeAuditRepository(
        {"c_000007": _tool_record("c_000007", "plain raw", json.dumps({"rows": [1, 2]}))}
    )
    harness = Harness(tool_call=FakeToolCall(outcome), audit_repository=repository)

    response = await harness.use_case.execute(_tool_request())

    assert response.raw_result == "plain raw"
    assert response.delivered_result == {"rows": [1, 2]}
    assert response.action is RuleAction.mask


@pytest.mark.asyncio
async def test_tool_trace_without_decision_falls_back_to_outcome_fields() -> None:
    outcome = ToolCallOutcome(
        call_id="c_000007",
        status=CallStatus.ESCALATED,
        stage=StageName.authorization,
        rule_id="destructive_requires_approval",
        reason="needs approval",
    )
    harness = Harness(tool_call=FakeToolCall(outcome))

    response = await harness.use_case.execute(_tool_request())

    assert response.status is CallStatus.ESCALATED
    assert response.action is RuleAction.require_approval
    assert response.stage is StageName.authorization
    assert response.rule_id == "destructive_requires_approval"
    assert response.stages == []
    assert response.raw_result is None
    assert response.delivered_result is None


@pytest.mark.asyncio
async def test_tool_trace_reads_decision_from_policy_violation_error() -> None:
    decision = _blocked_decision()
    error = PolicyViolationError(decision.violations[0], CallStatus.BLOCKED)
    error.call_id = "c_000009"
    error.decision = decision
    repository = FakeAuditRepository({"c_000009": _tool_record("c_000009", "secret raw", None)})
    harness = Harness(tool_call=FakeToolCall(error=error), audit_repository=repository)

    response = await harness.use_case.execute(_tool_request())

    assert response.call_id == "c_000009"
    assert response.status is CallStatus.BLOCKED
    assert response.action is RuleAction.block
    assert response.stage is StageName.policy
    assert response.rule_id == "prompt_injection_signatures"
    assert response.stages[-1].stage is StageName.audit
    assert response.raw_result == "secret raw"
    assert response.delivered_result is None


@pytest.mark.asyncio
async def test_tool_trace_error_without_decision_uses_violation_from_error() -> None:
    violation = _violation("direct_push_to_main", RuleAction.block, StageName.policy)
    error = PolicyViolationError(violation, CallStatus.BLOCKED)
    error.call_id = "c_000010"
    harness = Harness(tool_call=FakeToolCall(error=error))

    response = await harness.use_case.execute(_tool_request())

    assert response.status is CallStatus.BLOCKED
    assert response.action is RuleAction.block
    assert response.stage is StageName.policy
    assert response.rule_id == "direct_push_to_main"
    assert response.stages == []


@pytest.mark.asyncio
async def test_tool_trace_reraises_errors_that_were_never_audited() -> None:
    error: ControlLayerError = UnknownToolError("github", "nope")
    harness = Harness(tool_call=FakeToolCall(error=error))

    with pytest.raises(UnknownToolError):
        await harness.use_case.execute(_tool_request())
