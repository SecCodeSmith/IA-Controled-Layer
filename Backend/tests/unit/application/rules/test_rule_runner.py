from __future__ import annotations

from control_layer.application.rules.registry import EvaluatorRegistry
from control_layer.application.rules.rule_runner import RuleRunner
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.enums import InterceptionPoint, RuleAction, Severity, StageName
from control_layer.domain.policy.parser import parse_policy_document


class _FakeEvaluator:
    def __init__(self, outcome: RuleOutcome | list[RuleOutcome]) -> None:
        self._outcomes = outcome if isinstance(outcome, list) else [outcome]
        self.calls: list[tuple] = []

    async def evaluate(self, rule, ctx, policy):  # noqa: ANN001
        self.calls.append((rule.id, ctx.point))
        outcome = self._outcomes.pop(0) if len(self._outcomes) > 1 else self._outcomes[0]
        return outcome


def _ctx(
    point: InterceptionPoint = InterceptionPoint.prompt, text: str = "hello"
) -> ProcessingContext:
    return ProcessingContext(identity=None, point=point, text=text, session_id="s1", call_id="c1")


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


def test_filters_by_stage() -> None:
    registry = EvaluatorRegistry()
    matching = _FakeEvaluator(RuleOutcome(matched=True, reason="matched"))
    other_stage = _FakeEvaluator(RuleOutcome(matched=True, reason="should not run"))
    registry.register("detectors", matching)
    registry.register("rbac", other_stage)
    policy = _policy(
        [
            {"id": "r_dlp", "stage": "dlp", "detect": ["email"], "action": "mask"},
            {"id": "r_auth", "stage": "authorization", "type": "rbac", "action": "block"},
        ]
    )
    runner = RuleRunner(registry)
    result = runner.applicable_rules(StageName.dlp, _ctx(), policy)
    assert [r.id for r in result] == ["r_dlp"]


def test_filters_by_enabled() -> None:
    registry = EvaluatorRegistry()
    registry.register("detectors", _FakeEvaluator(RuleOutcome(matched=True)))
    policy = _policy(
        [
            {
                "id": "disabled_rule",
                "stage": "dlp",
                "detect": ["email"],
                "action": "mask",
                "enabled": False,
            }
        ]
    )
    runner = RuleRunner(registry)
    assert runner.applicable_rules(StageName.dlp, _ctx(), policy) == []


def test_filters_by_point() -> None:
    registry = EvaluatorRegistry()
    registry.register("detectors", _FakeEvaluator(RuleOutcome(matched=True)))
    policy = _policy(
        [
            {
                "id": "response_only",
                "stage": "dlp",
                "on": "response",
                "detect": ["email"],
                "action": "mask",
            }
        ]
    )
    runner = RuleRunner(registry)
    assert (
        runner.applicable_rules(StageName.dlp, _ctx(point=InterceptionPoint.prompt), policy) == []
    )
    assert (
        len(runner.applicable_rules(StageName.dlp, _ctx(point=InterceptionPoint.response), policy))
        == 1
    )


async def test_accumulates_masked_text_across_rules() -> None:
    registry = EvaluatorRegistry()
    registry.register(
        "detectors_a", _FakeEvaluator(RuleOutcome(matched=True, masked_text="step1", reason="a"))
    )
    registry.register(
        "detectors_b", _FakeEvaluator(RuleOutcome(matched=True, masked_text="step2", reason="b"))
    )
    policy = _policy(
        [
            {"id": "rule_a", "stage": "dlp", "type": "detectors_a", "action": "mask"},
            {"id": "rule_b", "stage": "dlp", "type": "detectors_b", "action": "mask"},
        ]
    )
    runner = RuleRunner(registry)
    ctx = _ctx()
    result = await runner.run(StageName.dlp, ctx, policy)
    assert ctx.masked_text == "step2"
    assert result.masked_text == "step2"
    assert result.action == RuleAction.mask


async def test_merges_action_and_picks_highest_precedence_reason() -> None:
    registry = EvaluatorRegistry()
    registry.register("flagger", _FakeEvaluator(RuleOutcome(matched=True, reason="flagged")))
    registry.register("blocker", _FakeEvaluator(RuleOutcome(matched=True, reason="blocked")))
    policy = _policy(
        [
            {"id": "flag_rule", "stage": "policy", "type": "flagger", "action": "flag"},
            {"id": "block_rule", "stage": "policy", "type": "blocker", "action": "block"},
        ]
    )
    runner = RuleRunner(registry)
    result = await runner.run(StageName.policy, _ctx(), policy)
    assert result.action == RuleAction.block
    assert result.reason == "blocked"
    assert {v.rule_id for v in result.violations} == {"flag_rule", "block_rule"}


async def test_allow_when_no_rule_matches() -> None:
    registry = EvaluatorRegistry()
    registry.register("detectors", _FakeEvaluator(RuleOutcome(matched=False)))
    policy = _policy([{"id": "r1", "stage": "dlp", "detect": ["email"], "action": "mask"}])
    runner = RuleRunner(registry)
    result = await runner.run(StageName.dlp, _ctx(), policy)
    assert result.action == RuleAction.allow
    assert result.violations == []
    assert result.reason is None


async def test_rule_filter_excludes_rules() -> None:
    registry = EvaluatorRegistry()
    registry.register("tool_match", _FakeEvaluator(RuleOutcome(matched=True, reason="matched")))
    policy = _policy(
        [
            {
                "id": "approval_rule",
                "stage": "authorization",
                "match": {"action": ["x"]},
                "action": "require_approval",
            }
        ]
    )
    runner = RuleRunner(registry)
    result = await runner.run(
        StageName.authorization,
        _ctx(),
        policy,
        rule_filter=lambda rule: rule.type != "tool_match",
    )
    assert result.action == RuleAction.allow
    assert result.violations == []


def test_severity_and_owasp_copied_from_rule() -> None:
    registry = EvaluatorRegistry()
    registry.register("detectors", _FakeEvaluator(RuleOutcome(matched=True, evidence=["email"])))
    policy = _policy(
        [
            {
                "id": "r1",
                "stage": "dlp",
                "detect": ["email"],
                "action": "mask",
                "severity": "high",
                "owasp": ["LLM02"],
            }
        ]
    )
    runner = RuleRunner(registry)
    evaluations = _run_sync(runner, StageName.dlp, _ctx(), policy)
    result = RuleRunner.build_stage_result(StageName.dlp, evaluations)
    assert result.violations[0].severity == Severity.high
    assert result.violations[0].owasp == ["LLM02"]
    assert result.violations[0].evidence == ["email"]


def _run_sync(runner: RuleRunner, stage, ctx, policy):  # noqa: ANN001
    import asyncio

    return asyncio.run(runner.evaluate_rules(stage, ctx, policy))
