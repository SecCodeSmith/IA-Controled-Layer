from __future__ import annotations

import pytest

from control_layer.application.use_cases.handle_tool_call import HandleToolCallUseCase
from control_layer.domain.exceptions import PolicyViolationError, UnknownToolError
from control_layer.domain.models.audit import CallRecord
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import Decision, Violation
from control_layer.domain.models.enums import (
    CallStatus,
    InterceptionPoint,
    Role,
    RuleAction,
    Severity,
    StageName,
)
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.provider import ProviderInfo
from control_layer.domain.models.session import SessionState
from control_layer.domain.models.tool import ToolCallRequest, ToolCallResult, ToolDescriptor


class _ScriptedPipeline:
    def __init__(self, steps: list[tuple[Decision, str | None]], identity: Identity) -> None:
        self._steps = list(steps)
        self._identity = identity
        self.contexts: list[ProcessingContext] = []

    async def run(self, ctx: ProcessingContext) -> Decision:
        self.contexts.append(ctx)
        if ctx.identity is None:
            ctx.identity = self._identity
        decision, masked_text = self._steps.pop(0)
        if masked_text is not None:
            ctx.masked_text = masked_text
        if ctx.point == InterceptionPoint.tool_result and ctx.metadata.get("injection_detected"):
            session_state = ctx.metadata.get("session_state")
            if session_state is not None:
                session_state.tainted = True
        return decision


class _FakeToolCatalog:
    def __init__(self, descriptor: ToolDescriptor) -> None:
        self._descriptor = descriptor

    async def provisioned_for(self, identity):  # noqa: ANN001, ANN201
        return [self._descriptor]

    async def descriptor(self, server: str, tool: str) -> ToolDescriptor:
        if server == self._descriptor.server and tool == self._descriptor.name:
            return self._descriptor
        raise UnknownToolError(server, tool)


class _FakeMcpGateway:
    def __init__(self, result: ToolCallResult) -> None:
        self._result = result
        self.calls: list[ToolCallRequest] = []

    async def list_tools(self):  # noqa: ANN201
        return []

    async def call_tool(self, request: ToolCallRequest) -> ToolCallResult:
        self.calls.append(request)
        return self._result


class _FakeApprovalService:
    def __init__(self) -> None:
        self.created: list[tuple] = []

    async def create(self, identity, tool_call, rule_id, reason):  # noqa: ANN001, ANN201
        self.created.append((identity, tool_call, rule_id, reason))
        from datetime import UTC, datetime

        from control_layer.domain.models.approval import PendingApproval
        from control_layer.domain.models.enums import ApprovalStatus

        return PendingApproval(
            id="ap_abc123abc123",
            identity=identity,
            tool_call=tool_call,
            created_at=datetime(2026, 10, 3, tzinfo=UTC),
            rule_id=rule_id,
            status=ApprovalStatus.pending,
            reason=reason,
        )

    async def get_for(self, identity, approval_id):  # noqa: ANN001, ANN201
        raise NotImplementedError

    async def mark(self, approval_id, status):  # noqa: ANN001
        raise NotImplementedError


class _FakeSessionService:
    def __init__(self, state: SessionState | None = None) -> None:
        self._state = state

    async def load(self, session_id: str) -> SessionState:
        return self._state or SessionState(session_id=session_id)

    async def save(self, state) -> None:  # noqa: ANN001
        pass


class _FakeAuditService:
    def __init__(self) -> None:
        self.records: list[tuple[CallRecord, Decision]] = []

    async def record(self, call, decision):  # noqa: ANN001, ANN201
        self.records.append((call, decision))
        return None


class _FakeCircuitBreaker:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def record_block(self, identity, call_id) -> None:  # noqa: ANN001
        self.calls.append((identity, call_id))


class _FakeRiskService:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def record(self, identity, decision):  # noqa: ANN001, ANN201
        self.calls.append((identity, decision))
        from control_layer.domain.models.risk import RiskProfile

        return RiskProfile(sub=identity.sub)


class _FakeCallIds:
    def __init__(self) -> None:
        self.n = 0

    async def next(self) -> str:
        self.n += 1
        return f"c_{self.n:06d}"


class _FakePolicyRepository:
    async def current(self):  # noqa: ANN201
        raise NotImplementedError

    async def reload(self):  # noqa: ANN201
        raise NotImplementedError

    async def status(self) -> dict:
        return {}


class _FakeModelProvider:
    async def complete(self, request):  # noqa: ANN001, ANN201
        raise NotImplementedError

    def describe(self) -> ProviderInfo:
        return ProviderInfo(name="ollama", model="qwen2.5:7b")


def _identity() -> Identity:
    return Identity(
        sub="anna.kowalska",
        name="Anna Kowalska",
        role=Role.developer,
        location="Krakow, PL",
        region="PL",
        agent_id="agent-anna-dev-7f3a",
    )


def _descriptor() -> ToolDescriptor:
    return ToolDescriptor(
        server="logs-db",
        name="query",
        qualified_name="logs-db.query",
        description="",
        input_schema={},
        tags=[],
        scope="read",
    )


def _violation(action: RuleAction, rule_id: str, stage: StageName) -> Violation:
    return Violation(
        stage=stage,
        rule_id=rule_id,
        action=action,
        severity=Severity.medium,
        owasp=[],
        evidence=[],
        confidence=1.0,
        reason=f"{rule_id} fired",
    )


def _build_use_case(pipeline, mcp_gateway=None, approval_service=None, session_service=None):  # noqa: ANN001
    return HandleToolCallUseCase(
        pipeline=pipeline,
        tool_catalog=_FakeToolCatalog(_descriptor()),
        mcp_gateway=mcp_gateway or _FakeMcpGateway(ToolCallResult(content_text="ok")),
        approval_service=approval_service or _FakeApprovalService(),
        session_service=session_service or _FakeSessionService(),
        audit_service=_FakeAuditService(),
        circuit_breaker=_FakeCircuitBreaker(),
        risk_service=_FakeRiskService(),
        call_ids=_FakeCallIds(),
        policy_repository=_FakePolicyRepository(),
        model_provider=_FakeModelProvider(),
    )


def _request() -> ToolCallRequest:
    return ToolCallRequest(server="logs-db", tool="query", arguments={"service": "auth"})


async def test_blocked_tool_call_never_reaches_gateway() -> None:
    violation = _violation(RuleAction.block, "role_provisioning", StageName.authorization)
    pipeline = _ScriptedPipeline(
        [
            (
                Decision(
                    status=CallStatus.BLOCKED, action=RuleAction.block, violations=[violation]
                ),
                None,
            )
        ],
        _identity(),
    )
    gateway = _FakeMcpGateway(ToolCallResult(content_text="should never be called"))
    use_case = _build_use_case(pipeline, mcp_gateway=gateway)

    with pytest.raises(PolicyViolationError):
        await use_case.execute("token", "s1", _request())

    assert gateway.calls == []
    assert len(use_case._audit_service.records) == 1
    assert use_case._audit_service.records[0][0].decision.status == CallStatus.BLOCKED


async def test_escalation_creates_approval_and_audits_escalated() -> None:
    violation = _violation(
        RuleAction.require_approval, "destructive_requires_approval", StageName.authorization
    )
    pipeline = _ScriptedPipeline(
        [
            (
                Decision(
                    status=CallStatus.ESCALATED,
                    action=RuleAction.require_approval,
                    violations=[violation],
                ),
                None,
            )
        ],
        _identity(),
    )
    approval_service = _FakeApprovalService()
    use_case = _build_use_case(pipeline, approval_service=approval_service)

    outcome = await use_case.execute("token", "s1", _request())

    assert outcome.status == CallStatus.ESCALATED
    assert outcome.approval is not None
    assert outcome.approval.id == "ap_abc123abc123"
    assert len(approval_service.created) == 1
    assert len(use_case._audit_service.records) == 1
    assert use_case._audit_service.records[0][0].decision.status == CallStatus.ESCALATED


async def test_masked_tool_result_is_delivered() -> None:
    violation = _violation(RuleAction.mask, "pii_masking", StageName.dlp)
    pipeline = _ScriptedPipeline(
        [
            (Decision(status=CallStatus.ALLOWED, action=RuleAction.allow), None),
            (
                Decision(status=CallStatus.MASKED, action=RuleAction.mask, violations=[violation]),
                "[EMAIL_1] seen",
            ),
        ],
        _identity(),
    )
    gateway = _FakeMcpGateway(ToolCallResult(content_text="t.lis@example.com seen"))
    use_case = _build_use_case(pipeline, mcp_gateway=gateway)

    outcome = await use_case.execute("token", "s1", _request())

    assert outcome.status == CallStatus.MASKED
    assert outcome.result.content_text == "[EMAIL_1] seen"
    assert outcome.items_masked == 1


async def test_taint_flag_set_when_tool_call_pass_had_policy_violation() -> None:
    injection_violation = _violation(
        RuleAction.block, "prompt_injection_signatures", StageName.policy
    )
    # tool_call pass is "allowed" overall (flag only) but still carries a policy-stage violation
    decision1 = Decision(
        status=CallStatus.FLAGGED, action=RuleAction.flag, violations=[injection_violation]
    )
    decision2 = Decision(status=CallStatus.ALLOWED, action=RuleAction.allow)
    pipeline = _ScriptedPipeline([(decision1, None), (decision2, None)], _identity())
    state = SessionState(session_id="s1")
    use_case = _build_use_case(pipeline, session_service=_FakeSessionService(state))

    await use_case.execute("token", "s1", _request())

    assert state.tainted is True


async def test_no_taint_when_no_injection_detected() -> None:
    pipeline = _ScriptedPipeline(
        [
            (Decision(status=CallStatus.ALLOWED, action=RuleAction.allow), None),
            (Decision(status=CallStatus.ALLOWED, action=RuleAction.allow), None),
        ],
        _identity(),
    )
    state = SessionState(session_id="s1")
    use_case = _build_use_case(pipeline, session_service=_FakeSessionService(state))

    await use_case.execute("token", "s1", _request())

    assert state.tainted is False
