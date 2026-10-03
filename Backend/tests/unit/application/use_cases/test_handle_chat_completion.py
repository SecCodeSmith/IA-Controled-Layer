from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from control_layer.application.use_cases.handle_chat_completion import HandleChatCompletionUseCase
from control_layer.domain.exceptions import PolicyViolationError, UpstreamProviderError
from control_layer.domain.models.audit import CallRecord
from control_layer.domain.models.budget_usage import BudgetUsage
from control_layer.domain.models.chat import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    Usage,
)
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import Decision, Violation
from control_layer.domain.models.enums import CallStatus, Role, RuleAction, Severity, StageName
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.provider import ProviderInfo
from control_layer.domain.models.risk import RiskProfile
from control_layer.domain.policy.parser import parse_policy_document


class _ScriptedPipeline:
    def __init__(self, steps: list[tuple[Decision, str | None]]) -> None:
        self._steps = list(steps)
        self.contexts: list[ProcessingContext] = []

    async def run(self, ctx: ProcessingContext) -> Decision:
        self.contexts.append(ctx)
        decision, masked_text = self._steps.pop(0)
        if masked_text is not None:
            ctx.masked_text = masked_text
        return decision


class _FakeIdentityService:
    def __init__(self, identity: Identity) -> None:
        self._identity = identity

    async def resolve(self, token: str, session_id: str) -> Identity:
        return self._identity.model_copy(update={"session_id": session_id})


class _FakeModelProvider:
    def __init__(self, response=None, error=None, delay: float = 0.0) -> None:  # noqa: ANN001
        self._response = response
        self._error = error
        self._delay = delay
        self.requests: list[ChatCompletionRequest] = []

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        self.requests.append(request)
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._error:
            raise self._error
        return self._response

    def describe(self) -> ProviderInfo:
        return ProviderInfo(name="mock", model="mock")


class _FakeBudgetService:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def record(self, identity, usage, model, policy) -> BudgetUsage:  # noqa: ANN001
        self.calls.append((identity, usage, model))
        return BudgetUsage(
            tokens_used=usage.total_tokens,
            tokens_limit=10000,
            cost_used_usd=0.0,
            cost_limit_usd=1.0,
            resets_at=datetime(2026, 10, 5, tzinfo=UTC),
        )


class _FakeSessionService:
    async def load(self, session_id: str):  # noqa: ANN201
        from control_layer.domain.models.session import SessionState

        return SessionState(session_id=session_id)

    async def save(self, state) -> None:  # noqa: ANN001
        pass


class _FakeAuditService:
    def __init__(self) -> None:
        self.records: list[tuple[CallRecord, Decision]] = []

    async def record(self, call: CallRecord, decision: Decision):  # noqa: ANN201
        self.records.append((call, decision))
        return None


class _FakeCircuitBreaker:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def record_block(self, identity, call_id: str) -> None:  # noqa: ANN001
        self.calls.append((identity, call_id))


class _FakeRiskService:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def record(self, identity, decision: Decision) -> RiskProfile:  # noqa: ANN001
        self.calls.append((identity, decision))
        return RiskProfile(sub=identity.sub)


class _FakeCallIds:
    def __init__(self) -> None:
        self.n = 0

    async def next(self) -> str:
        self.n += 1
        return f"c_{self.n:06d}"


class _FakePolicyRepository:
    def __init__(self, policy) -> None:  # noqa: ANN001
        self._policy = policy

    async def current(self):  # noqa: ANN201
        return self._policy

    async def reload(self):  # noqa: ANN201
        return self._policy

    async def status(self) -> dict:
        return {}


def _policy(upstream_timeout_s: float = 30, canary_rule: bool = False):
    rules = []
    if canary_rule:
        rules.append({"id": "canary_token", "type": "canary_token", "action": "flag"})
    data = {
        "version": 1,
        "profile": "balanced",
        "models": {
            "allowed": ["mock-model"],
            "pricing": {"mock-model": {"input_per_1k_usd": 0.001, "output_per_1k_usd": 0.002}},
        },
        "roles": {},
        "locations": {},
        "rules": rules,
        "budgets": {
            "per_user_tokens": 10000,
            "per_user_cost_usd": 1.0,
            "max_tokens_per_request": 2048,
            "upstream_timeout_s": upstream_timeout_s,
            "warn_at_percent": 80,
            "on_exceeded": "block",
        },
    }
    return parse_policy_document(data, source_hash="h")


def _identity() -> Identity:
    return Identity(
        sub="anna.kowalska",
        name="Anna Kowalska",
        role=Role.developer,
        location="Krakow, PL",
        region="PL",
        agent_id="agent-anna-dev-7f3a",
    )


def _request(message: str = "hello", system: str | None = None) -> ChatCompletionRequest:
    messages = []
    if system is not None:
        messages.append(ChatMessage(role="system", content=system))
    messages.append(ChatMessage(role="user", content=message))
    return ChatCompletionRequest(model="mock-model", messages=messages)


def _response(content: str = "hi there") -> ChatCompletionResponse:
    return ChatCompletionResponse(
        id="resp1",
        created=1,
        model="mock-model",
        choices=[
            ChatCompletionChoice(index=0, message=ChatMessage(role="assistant", content=content))
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


def _violation(action: RuleAction, rule_id: str, stage: StageName = StageName.dlp) -> Violation:
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


def _build_use_case(pipeline, policy=None, model_provider=None, budget_service=None):  # noqa: ANN001
    return (
        HandleChatCompletionUseCase(
            pipeline=pipeline,
            identity_service=_FakeIdentityService(_identity()),
            model_provider=model_provider or _FakeModelProvider(response=_response()),
            budget_service=budget_service or _FakeBudgetService(),
            session_service=_FakeSessionService(),
            audit_service=_FakeAuditService(),
            circuit_breaker=_FakeCircuitBreaker(),
            risk_service=_FakeRiskService(),
            call_ids=_FakeCallIds(),
            policy_repository=_FakePolicyRepository(policy or _policy()),
            canary_token="CANARY-XYZ",
        ),
    )[0]


async def test_blocked_prompt_never_calls_provider_and_still_audits() -> None:
    violation = _violation(RuleAction.block, "role_provisioning", StageName.authorization)
    pipeline = _ScriptedPipeline(
        [
            (
                Decision(
                    status=CallStatus.BLOCKED, action=RuleAction.block, violations=[violation]
                ),
                None,
            )
        ]
    )
    provider = _FakeModelProvider(response=_response())
    use_case = _build_use_case(pipeline, model_provider=provider)

    with pytest.raises(PolicyViolationError):
        await use_case.execute("token", "s1", _request())

    assert provider.requests == []
    assert len(use_case._audit_service.records) == 1
    assert use_case._audit_service.records[0][0].decision.status == CallStatus.BLOCKED


async def test_masked_prompt_is_forwarded_to_provider() -> None:
    violation = _violation(RuleAction.mask, "secrets_detection")
    pipeline = _ScriptedPipeline(
        [
            (
                Decision(status=CallStatus.MASKED, action=RuleAction.mask, violations=[violation]),
                "[API_KEY_1] please redeploy",
            ),
            (Decision(status=CallStatus.ALLOWED, action=RuleAction.allow), None),
        ]
    )
    provider = _FakeModelProvider(response=_response())
    use_case = _build_use_case(pipeline, model_provider=provider)

    await use_case.execute("token", "s1", _request("my secret key sk_live_xxx please redeploy"))

    sent_messages = provider.requests[0].messages
    assert sent_messages[-1].content == "[API_KEY_1] please redeploy"


async def test_canary_appended_only_when_rule_enabled() -> None:
    pipeline = _ScriptedPipeline(
        [
            (Decision(status=CallStatus.ALLOWED, action=RuleAction.allow), None),
            (Decision(status=CallStatus.ALLOWED, action=RuleAction.allow), None),
        ]
    )
    provider = _FakeModelProvider(response=_response())
    use_case = _build_use_case(pipeline, policy=_policy(canary_rule=True), model_provider=provider)

    await use_case.execute("token", "s1", _request(system="be helpful"))

    system_message = next(m for m in provider.requests[0].messages if m.role == "system")
    assert "CANARY-XYZ" in system_message.content


async def test_canary_not_appended_when_rule_disabled() -> None:
    pipeline = _ScriptedPipeline(
        [
            (Decision(status=CallStatus.ALLOWED, action=RuleAction.allow), None),
            (Decision(status=CallStatus.ALLOWED, action=RuleAction.allow), None),
        ]
    )
    provider = _FakeModelProvider(response=_response())
    use_case = _build_use_case(pipeline, policy=_policy(canary_rule=False), model_provider=provider)

    await use_case.execute("token", "s1", _request(system="be helpful"))

    system_message = next(m for m in provider.requests[0].messages if m.role == "system")
    assert "CANARY-XYZ" not in system_message.content


async def test_upstream_timeout_raises_upstream_provider_error_and_audits() -> None:
    pipeline = _ScriptedPipeline(
        [(Decision(status=CallStatus.ALLOWED, action=RuleAction.allow), None)]
    )
    provider = _FakeModelProvider(response=_response(), delay=0.2)
    use_case = _build_use_case(
        pipeline, policy=_policy(upstream_timeout_s=0), model_provider=provider
    )

    with pytest.raises(UpstreamProviderError):
        await use_case.execute("token", "s1", _request())

    assert len(use_case._audit_service.records) == 1
    assert use_case._audit_service.records[0][0].decision.reason == "Upstream provider timed out"


async def test_blocked_response_raises_after_audit() -> None:
    violation = _violation(RuleAction.block, "prompt_injection_signatures", StageName.policy)
    pipeline = _ScriptedPipeline(
        [
            (Decision(status=CallStatus.ALLOWED, action=RuleAction.allow), None),
            (
                Decision(
                    status=CallStatus.BLOCKED, action=RuleAction.block, violations=[violation]
                ),
                None,
            ),
        ]
    )
    use_case = _build_use_case(pipeline)

    with pytest.raises(PolicyViolationError):
        await use_case.execute("token", "s1", _request())

    assert len(use_case._audit_service.records) == 1
    assert use_case._audit_service.records[0][0].decision.status == CallStatus.BLOCKED


async def test_masked_response_delivered_with_items_masked() -> None:
    violation = _violation(RuleAction.mask, "pii_masking")
    pipeline = _ScriptedPipeline(
        [
            (Decision(status=CallStatus.ALLOWED, action=RuleAction.allow), None),
            (
                Decision(status=CallStatus.MASKED, action=RuleAction.mask, violations=[violation]),
                "[EMAIL_1] said hi",
            ),
        ]
    )
    use_case = _build_use_case(pipeline)

    outcome = await use_case.execute("token", "s1", _request())

    assert outcome.status == CallStatus.MASKED
    assert outcome.items_masked == 1
    assert outcome.response.choices[0].message.content == "[EMAIL_1] said hi"


async def test_usage_is_recorded_after_successful_call() -> None:
    pipeline = _ScriptedPipeline(
        [
            (Decision(status=CallStatus.ALLOWED, action=RuleAction.allow), None),
            (Decision(status=CallStatus.ALLOWED, action=RuleAction.allow), None),
        ]
    )
    budget_service = _FakeBudgetService()
    use_case = _build_use_case(pipeline, budget_service=budget_service)

    await use_case.execute("token", "s1", _request())

    assert len(budget_service.calls) == 1
    identity, usage, model = budget_service.calls[0]
    assert identity.sub == "anna.kowalska"
    assert usage.total_tokens == 15
    assert model == "mock-model"


async def test_outcome_fields_on_successful_allowed_call() -> None:
    pipeline = _ScriptedPipeline(
        [
            (Decision(status=CallStatus.ALLOWED, action=RuleAction.allow), None),
            (Decision(status=CallStatus.ALLOWED, action=RuleAction.allow), None),
        ]
    )
    use_case = _build_use_case(pipeline)

    outcome = await use_case.execute("token", "s1", _request())

    assert outcome.call_id == "c_000001"
    assert outcome.status == CallStatus.ALLOWED
    assert outcome.stage is None
    assert outcome.rule_id is None
    assert outcome.reason is None
    assert outcome.items_masked == 0
    assert outcome.proxy_latency_ms >= 0
    assert outcome.upstream_latency_ms >= 0
    assert outcome.response.choices[0].message.content == "hi there"
