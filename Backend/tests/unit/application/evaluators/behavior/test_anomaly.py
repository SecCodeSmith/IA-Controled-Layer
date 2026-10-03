from control_layer.application.evaluators.behavior.anomaly import AnomalyEvaluator
from tests.unit.application.evaluators.conftest import (
    FakeCacheRepository,
    make_context,
    make_descriptor,
    make_identity,
    make_policy,
)
from tests.unit.application.evaluators.conftest import make_rule as _make_rule


def make_rule(**kwargs):
    kwargs.setdefault("rule_type", "anomaly")
    return _make_rule(**kwargs)


async def test_first_use_of_destructive_tool_is_matched() -> None:
    cache = FakeCacheRepository()
    evaluator = AnomalyEvaluator(cache)
    rule = make_rule()
    policy = make_policy()
    ctx = make_context(
        identity=make_identity(sub="anna"),
        metadata={
            "tool_descriptor": make_descriptor(
                server="github", name="delete_branch", tags=["destructive"]
            )
        },
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.confidence == 0.3
    assert outcome.reason == "First use of a destructive tool"


async def test_second_use_of_destructive_tool_is_not_matched() -> None:
    cache = FakeCacheRepository()
    evaluator = AnomalyEvaluator(cache)
    rule = make_rule()
    policy = make_policy()
    ctx = make_context(
        identity=make_identity(sub="anna"),
        metadata={
            "tool_descriptor": make_descriptor(
                server="github", name="delete_branch", tags=["destructive"]
            )
        },
    )

    await evaluator.evaluate(rule, ctx, policy)
    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_non_destructive_tool_is_never_matched() -> None:
    cache = FakeCacheRepository()
    evaluator = AnomalyEvaluator(cache)
    rule = make_rule()
    policy = make_policy()
    ctx = make_context(
        identity=make_identity(sub="anna"),
        metadata={"tool_descriptor": make_descriptor(server="github", name="get_readme", tags=[])},
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_different_users_have_independent_first_use_state() -> None:
    cache = FakeCacheRepository()
    evaluator = AnomalyEvaluator(cache)
    rule = make_rule()
    policy = make_policy()
    descriptor = make_descriptor(server="github", name="delete_branch", tags=["destructive"])

    ctx_anna = make_context(
        identity=make_identity(sub="anna"), metadata={"tool_descriptor": descriptor}
    )
    ctx_marek = make_context(
        identity=make_identity(sub="marek"), metadata={"tool_descriptor": descriptor}
    )

    await evaluator.evaluate(rule, ctx_anna, policy)
    outcome_marek = await evaluator.evaluate(rule, ctx_marek, policy)

    assert outcome_marek.matched is True


async def test_missing_descriptor_is_not_matched() -> None:
    cache = FakeCacheRepository()
    evaluator = AnomalyEvaluator(cache)
    rule = make_rule()
    policy = make_policy()
    ctx = make_context(identity=make_identity(sub="anna"), metadata={})

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False
