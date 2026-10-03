from control_layer.application.evaluators.authorization.model_allowlist import (
    ModelAllowlistEvaluator,
)
from control_layer.domain.models.enums import InterceptionPoint
from tests.unit.application.evaluators.conftest import make_context, make_policy, make_rule


async def test_non_prompt_point_is_not_matched() -> None:
    evaluator = ModelAllowlistEvaluator()
    rule = make_rule(rule_type="model_allowlist")
    policy = make_policy(models={"allowed": ["qwen2.5:7b"], "pricing": {}})
    ctx = make_context(point=InterceptionPoint.tool_call, metadata={"model": "forbidden-model"})

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_allowed_model_is_not_matched() -> None:
    evaluator = ModelAllowlistEvaluator()
    rule = make_rule(rule_type="model_allowlist")
    policy = make_policy(models={"allowed": ["qwen2.5:7b"], "pricing": {}})
    ctx = make_context(point=InterceptionPoint.prompt, metadata={"model": "qwen2.5:7b"})

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_disallowed_model_is_matched() -> None:
    evaluator = ModelAllowlistEvaluator()
    rule = make_rule(rule_type="model_allowlist")
    policy = make_policy(models={"allowed": ["qwen2.5:7b"], "pricing": {}})
    ctx = make_context(point=InterceptionPoint.prompt, metadata={"model": "gpt-4"})

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert "gpt-4" in (outcome.reason or "")


async def test_missing_model_metadata_is_not_matched() -> None:
    evaluator = ModelAllowlistEvaluator()
    rule = make_rule(rule_type="model_allowlist")
    policy = make_policy()
    ctx = make_context(point=InterceptionPoint.prompt, metadata={})

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False
