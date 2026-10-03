from __future__ import annotations

from control_layer.application.pipeline.stages.behavior import BehaviorStage
from control_layer.application.rules.registry import EvaluatorRegistry
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.enums import InterceptionPoint, StageName
from control_layer.domain.models.session import SessionState
from control_layer.domain.models.tool import ToolDescriptor
from control_layer.domain.policy.parser import parse_policy_document


class _NoMatch:
    async def evaluate(self, rule, ctx, policy):  # noqa: ANN001
        return RuleOutcome(matched=False)


class _FakeSessionRepository:
    def __init__(self) -> None:
        self.saved: list[SessionState] = []

    async def get(self, session_id: str) -> SessionState:
        return SessionState(session_id=session_id)

    async def save(self, state: SessionState) -> None:
        self.saved.append(state)

    async def clear(self, session_id: str | None = None) -> None:
        self.saved.clear()


def _policy():
    data = {
        "version": 1,
        "profile": "balanced",
        "models": {"allowed": ["mock"], "pricing": {}},
        "roles": {},
        "locations": {},
        "rules": [],
        "budgets": {
            "per_user_tokens": 1000,
            "per_user_cost_usd": 1.0,
            "max_tokens_per_request": 100,
            "upstream_timeout_s": 30,
            "warn_at_percent": 80,
            "on_exceeded": "block",
        },
    }
    return parse_policy_document(data, source_hash="h")


def _ctx(point: InterceptionPoint, metadata: dict | None = None) -> ProcessingContext:
    return ProcessingContext(
        identity=None,
        point=point,
        text="hi",
        session_id="s1",
        call_id="c1",
        metadata=metadata or {},
    )


async def test_persists_session_state_on_every_point() -> None:
    repo = _FakeSessionRepository()
    stage = BehaviorStage(EvaluatorRegistry(), repo)
    ctx = _ctx(InterceptionPoint.prompt, {"session_state": SessionState(session_id="s1")})
    await stage.process(ctx, _policy())
    assert len(repo.saved) == 1
    assert repo.saved[0].session_id == "s1"


async def test_tool_result_adds_descriptor_tags_to_session_state() -> None:
    repo = _FakeSessionRepository()
    stage = BehaviorStage(EvaluatorRegistry(), repo)
    descriptor = ToolDescriptor(
        server="github",
        name="get_readme",
        qualified_name="github.get_readme",
        description="",
        input_schema={},
        tags=["read_external"],
        scope="read",
    )
    state = SessionState(session_id="s1")
    ctx = _ctx(
        InterceptionPoint.tool_result, {"session_state": state, "tool_descriptor": descriptor}
    )
    await stage.process(ctx, _policy())
    assert "read_external" in repo.saved[0].tags_seen


async def test_tool_result_sets_tainted_when_injection_detected_flag_present() -> None:
    repo = _FakeSessionRepository()
    stage = BehaviorStage(EvaluatorRegistry(), repo)
    state = SessionState(session_id="s1")
    ctx = _ctx(InterceptionPoint.tool_result, {"session_state": state, "injection_detected": True})
    await stage.process(ctx, _policy())
    assert repo.saved[0].tainted is True


async def test_non_tool_result_point_does_not_mutate_taint() -> None:
    repo = _FakeSessionRepository()
    stage = BehaviorStage(EvaluatorRegistry(), repo)
    state = SessionState(session_id="s1")
    ctx = _ctx(InterceptionPoint.prompt, {"session_state": state, "injection_detected": True})
    await stage.process(ctx, _policy())
    assert repo.saved[0].tainted is False


def test_stage_name_is_behavior() -> None:
    assert BehaviorStage(EvaluatorRegistry(), _FakeSessionRepository()).name == StageName.behavior
