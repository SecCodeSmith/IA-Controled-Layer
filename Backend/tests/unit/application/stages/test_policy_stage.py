from __future__ import annotations

from control_layer.application.pipeline.stages.policy import PolicyStage
from control_layer.application.rules.registry import EvaluatorRegistry
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.enums import InterceptionPoint, RuleAction, StageName
from control_layer.domain.policy.parser import parse_policy_document


class _ScriptedEvaluator:
    def __init__(self, outcome: RuleOutcome) -> None:
        self._outcome = outcome
        self.called = False

    async def evaluate(self, rule, ctx, policy):  # noqa: ANN001
        self.called = True
        return self._outcome


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


def _ctx() -> ProcessingContext:
    return ProcessingContext(
        identity=None, point=InterceptionPoint.prompt, text="hi", session_id="s1", call_id="c1"
    )


async def test_inconclusive_ml_classifier_escalates_to_judge_rule() -> None:
    registry = EvaluatorRegistry()
    ml_evaluator = _ScriptedEvaluator(RuleOutcome(matched=False, inconclusive=True, reason="unsure"))
    judge_evaluator = _ScriptedEvaluator(RuleOutcome(matched=True, reason="judged block"))
    registry.register("ml_classifier", ml_evaluator)
    registry.register("llm_judge", judge_evaluator)
    rules = [
        {
            "id": "prompt_injection_ml",
            "type": "ml_classifier",
            "action": "flag",
            "escalate_to": "llm_judge",
        },
        {"id": "llm_judge", "on": [], "type": "llm_judge", "action": "block"},
    ]
    stage = PolicyStage(registry)
    ctx = _ctx()
    result = await stage.process(ctx, _policy(rules))
    assert judge_evaluator.called is True
    assert result.action == RuleAction.block
    assert [v.rule_id for v in result.violations] == ["llm_judge"]
    assert ctx.metadata.get("injection_detected") is True


async def test_inconclusive_without_escalation_target_becomes_flag_violation() -> None:
    registry = EvaluatorRegistry()
    ml_evaluator = _ScriptedEvaluator(RuleOutcome(matched=False, inconclusive=True, reason="unsure"))
    registry.register("ml_classifier", ml_evaluator)
    rules = [{"id": "prompt_injection_ml", "type": "ml_classifier", "action": "block"}]
    stage = PolicyStage(registry)
    ctx = _ctx()
    result = await stage.process(ctx, _policy(rules))
    assert result.action == RuleAction.flag
    assert result.violations[0].rule_id == "prompt_injection_ml"
    assert result.violations[0].reason == "unsure"
    assert ctx.metadata.get("injection_detected") is True


async def test_inconclusive_escalation_target_disabled_falls_back_to_flag() -> None:
    registry = EvaluatorRegistry()
    ml_evaluator = _ScriptedEvaluator(RuleOutcome(matched=False, inconclusive=True, reason="unsure"))
    registry.register("ml_classifier", ml_evaluator)
    rules = [
        {
            "id": "prompt_injection_ml",
            "type": "ml_classifier",
            "action": "block",
            "escalate_to": "llm_judge",
        },
        {"id": "llm_judge", "type": "llm_judge", "action": "block", "enabled": False},
    ]
    stage = PolicyStage(registry)
    result = await stage.process(_ctx(), _policy(rules))
    assert result.action == RuleAction.flag
    assert result.violations[0].rule_id == "prompt_injection_ml"


async def test_non_injection_matched_rule_does_not_set_injection_flag() -> None:
    registry = EvaluatorRegistry()
    registry.register("transaction_limit", _ScriptedEvaluator(RuleOutcome(matched=True, reason="over limit")))
    rules = [{"id": "over_limit", "type": "transaction_limit", "action": "block"}]
    stage = PolicyStage(registry)
    ctx = _ctx()
    await stage.process(ctx, _policy(rules))
    assert "injection_detected" not in ctx.metadata


def test_stage_name_is_policy() -> None:
    assert PolicyStage(EvaluatorRegistry()).name == StageName.policy
