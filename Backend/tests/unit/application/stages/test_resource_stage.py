from __future__ import annotations

from datetime import UTC, datetime

from control_layer.application.pipeline.stages.resource import ResourceStage
from control_layer.domain.models.budget_usage import BudgetUsage
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.enums import InterceptionPoint, Role, RuleAction, StageName
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.session import SessionState
from control_layer.domain.policy.parser import parse_policy_document


class _FakeBudgetRepository:
    def __init__(self, usage: BudgetUsage) -> None:
        self._usage = usage

    async def get_usage(self, sub: str) -> BudgetUsage:
        return self._usage

    async def record_usage(self, sub: str, tokens: int, cost_usd: float) -> BudgetUsage:
        raise NotImplementedError

    async def reset(self, sub: str | None = None) -> None:
        raise NotImplementedError


def _usage(tokens_used: int = 0, cost_used: float = 0.0) -> BudgetUsage:
    return BudgetUsage(
        tokens_used=tokens_used,
        tokens_limit=10000,
        cost_used_usd=cost_used,
        cost_limit_usd=1.0,
        resets_at=datetime(2026, 10, 5, tzinfo=UTC),
    )


def _policy(**budget_overrides):  # noqa: ANN003
    budgets = {
        "per_user_tokens": 10000,
        "per_user_cost_usd": 1.0,
        "max_tokens_per_request": 2048,
        "upstream_timeout_s": 30,
        "warn_at_percent": 80,
        "on_exceeded": "block",
    }
    budgets.update(budget_overrides)
    data = {
        "version": 1,
        "profile": "balanced",
        "models": {"allowed": ["mock"], "pricing": {}},
        "roles": {},
        "locations": {},
        "rules": [],
        "budgets": budgets,
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


def _ctx(point: InterceptionPoint, metadata: dict | None = None) -> ProcessingContext:
    return ProcessingContext(
        identity=_identity(),
        point=point,
        text="hi",
        session_id="s1",
        call_id="c1",
        metadata=metadata or {},
    )


async def test_blocks_when_tokens_over_budget() -> None:
    stage = ResourceStage(_FakeBudgetRepository(_usage(tokens_used=10000)))
    result = await stage.process(_ctx(InterceptionPoint.prompt), _policy())
    assert result.action == RuleAction.block
    assert result.reason == "Token budget overrun"


async def test_flags_instead_of_block_when_on_exceeded_is_warn() -> None:
    stage = ResourceStage(_FakeBudgetRepository(_usage(tokens_used=10000)))
    result = await stage.process(_ctx(InterceptionPoint.prompt), _policy(on_exceeded="warn"))
    assert result.action == RuleAction.flag


async def test_flags_at_warn_threshold() -> None:
    stage = ResourceStage(_FakeBudgetRepository(_usage(tokens_used=8500)))
    result = await stage.process(_ctx(InterceptionPoint.prompt), _policy())
    assert result.action == RuleAction.flag
    assert "85" in result.reason


async def test_allows_under_warn_threshold() -> None:
    stage = ResourceStage(_FakeBudgetRepository(_usage(tokens_used=100)))
    result = await stage.process(_ctx(InterceptionPoint.prompt), _policy())
    assert result.action == RuleAction.allow


async def test_caps_max_tokens_above_request_limit() -> None:
    stage = ResourceStage(_FakeBudgetRepository(_usage(tokens_used=100)))
    ctx = _ctx(InterceptionPoint.prompt, {"max_tokens": 5000})
    result = await stage.process(ctx, _policy())
    assert result.action == RuleAction.flag
    assert ctx.metadata["max_tokens"] == 2048


async def test_tool_call_quota_blocks_when_exceeded() -> None:
    stage = ResourceStage(_FakeBudgetRepository(_usage()))
    state = SessionState(session_id="s1", call_hashes=["a", "b", "c"])
    ctx = _ctx(InterceptionPoint.tool_call, {"session_state": state})
    result = await stage.process(ctx, _policy(tool_calls_per_session=3))
    assert result.action == RuleAction.block


async def test_tool_call_quota_unlimited_by_default() -> None:
    stage = ResourceStage(_FakeBudgetRepository(_usage()))
    state = SessionState(session_id="s1", call_hashes=["a", "b", "c", "d", "e"])
    ctx = _ctx(InterceptionPoint.tool_call, {"session_state": state})
    result = await stage.process(ctx, _policy())
    assert result.action == RuleAction.allow


async def test_response_point_is_a_no_op() -> None:
    stage = ResourceStage(_FakeBudgetRepository(_usage(tokens_used=999999)))
    result = await stage.process(_ctx(InterceptionPoint.response), _policy())
    assert result.action == RuleAction.allow


def test_stage_name_is_resource() -> None:
    assert ResourceStage(_FakeBudgetRepository(_usage())).name == StageName.resource
