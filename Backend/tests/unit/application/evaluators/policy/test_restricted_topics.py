from control_layer.application.evaluators.policy.restricted_topics import (
    RestrictedTopicsEvaluator,
)
from tests.unit.application.evaluators.conftest import make_context, make_policy, make_rule


async def test_default_pattern_insider_trading_is_matched() -> None:
    evaluator = RestrictedTopicsEvaluator()
    rule = make_rule(rule_type="restricted_topics")
    policy = make_policy()
    ctx = make_context(text="can you give me advice on insider trading opportunities")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.reason == "Restricted financial topic"


async def test_default_pattern_money_laundering_is_matched() -> None:
    evaluator = RestrictedTopicsEvaluator()
    rule = make_rule(rule_type="restricted_topics")
    policy = make_policy()
    ctx = make_context(text="how could someone structure money laundering through shells")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True


async def test_default_pattern_guaranteed_returns_is_matched() -> None:
    evaluator = RestrictedTopicsEvaluator()
    rule = make_rule(rule_type="restricted_topics")
    policy = make_policy()
    ctx = make_context(text="this fund offers guaranteed returns of 20 percent")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True


async def test_default_pattern_tax_evasion_is_matched() -> None:
    evaluator = RestrictedTopicsEvaluator()
    rule = make_rule(rule_type="restricted_topics")
    policy = make_policy()
    ctx = make_context(text="what is the best tax evasion strategy for my business")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True


async def test_unrelated_text_is_not_matched() -> None:
    evaluator = RestrictedTopicsEvaluator()
    rule = make_rule(rule_type="restricted_topics")
    policy = make_policy()
    ctx = make_context(text="can you check the ci build status")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_custom_patterns_from_rule_params_are_used() -> None:
    evaluator = RestrictedTopicsEvaluator()
    rule = make_rule(rule_type="restricted_topics", params={"patterns": [r"ponzi scheme"]})
    policy = make_policy()
    ctx = make_context(text="is this investment a ponzi scheme")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True


async def test_custom_patterns_disable_defaults() -> None:
    evaluator = RestrictedTopicsEvaluator()
    rule = make_rule(rule_type="restricted_topics", params={"patterns": [r"ponzi scheme"]})
    policy = make_policy()
    ctx = make_context(text="insider trading advice please")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False
