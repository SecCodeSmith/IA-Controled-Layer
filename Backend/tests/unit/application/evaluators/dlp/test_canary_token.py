from control_layer.application.evaluators.dlp.canary_token import CanaryTokenEvaluator
from tests.unit.application.evaluators.conftest import make_context, make_policy, make_rule


async def test_token_present_in_text_is_matched() -> None:
    evaluator = CanaryTokenEvaluator(token="CANARY-XYZ-123")
    rule = make_rule(rule_type="canary_token")
    policy = make_policy()
    ctx = make_context(text="here is some leaked text CANARY-XYZ-123 at the end")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.reason == "System prompt canary leaked"


async def test_token_absent_is_not_matched() -> None:
    evaluator = CanaryTokenEvaluator(token="CANARY-XYZ-123")
    rule = make_rule(rule_type="canary_token")
    policy = make_policy()
    ctx = make_context(text="nothing suspicious in this response")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_empty_token_never_matches() -> None:
    evaluator = CanaryTokenEvaluator(token="")
    rule = make_rule(rule_type="canary_token")
    policy = make_policy()
    ctx = make_context(text="")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False
