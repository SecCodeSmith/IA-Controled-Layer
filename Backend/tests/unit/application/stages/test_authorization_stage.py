from __future__ import annotations

from control_layer.application.pipeline.stages.authorization import AuthorizationStage
from control_layer.application.rules.registry import EvaluatorRegistry
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.enums import InterceptionPoint, RuleAction, StageName
from control_layer.domain.models.tool import ToolCallRequest, ToolDescriptor
from control_layer.domain.policy.parser import parse_policy_document


class _AlwaysMatches:
    async def evaluate(self, rule, ctx, policy):  # noqa: ANN001
        return RuleOutcome(matched=True, reason=f"matched {rule.id}")


def _policy(rules: list[dict]):
    data = {
        "version": 1,
        "profile": "balanced",
        "models": {"allowed": ["mock"], "pricing": {}},
        "roles": {},
        "locations": {},
        "rules": rules,
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


def _ctx(approved: bool = False) -> ProcessingContext:
    descriptor = ToolDescriptor(
        server="github",
        name="delete_branch",
        qualified_name="github.delete_branch",
        description="",
        input_schema={},
        tags=["destructive"],
        scope="write",
    )
    return ProcessingContext(
        identity=None,
        point=InterceptionPoint.tool_call,
        text="{}",
        tool_call=ToolCallRequest(server="github", tool="delete_branch", arguments={}),
        session_id="s1",
        call_id="c1",
        metadata={"approved": approved, "tool_descriptor": descriptor},
    )


def _rule_dict() -> dict:
    return {
        "id": "destructive_requires_approval",
        "match": {"action": ["delete_*"]},
        "action": "require_approval",
    }


async def test_require_approval_outcome_wins() -> None:
    registry = EvaluatorRegistry()
    registry.register("tool_match", _AlwaysMatches())
    stage = AuthorizationStage(registry)
    result = await stage.process(_ctx(), _policy([_rule_dict()]))
    assert result.action == RuleAction.require_approval
    assert result.violations[0].rule_id == "destructive_requires_approval"


async def test_approved_flag_skips_tool_match_rules() -> None:
    registry = EvaluatorRegistry()
    registry.register("tool_match", _AlwaysMatches())
    stage = AuthorizationStage(registry)
    result = await stage.process(_ctx(approved=True), _policy([_rule_dict()]))
    assert result.action == RuleAction.allow
    assert result.violations == []


def test_stage_name_is_authorization() -> None:
    stage = AuthorizationStage(EvaluatorRegistry())
    assert stage.name == StageName.authorization


async def test_rbac_rules_still_run_when_approved() -> None:
    registry = EvaluatorRegistry()
    registry.register("tool_match", _AlwaysMatches())
    registry.register("rbac", _AlwaysMatches())
    stage = AuthorizationStage(registry)
    rules = [_rule_dict(), {"id": "role_provisioning", "type": "rbac", "action": "block"}]
    result = await stage.process(_ctx(approved=True), _policy(rules))
    assert result.action == RuleAction.block
    assert [v.rule_id for v in result.violations] == ["role_provisioning"]
