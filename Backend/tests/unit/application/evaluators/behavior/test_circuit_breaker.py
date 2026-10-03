from control_layer.application.evaluators.behavior.circuit_breaker import CircuitBreakerEvaluator
from tests.unit.application.evaluators.conftest import (
    FakeCacheRepository,
    make_context,
    make_identity,
    make_policy,
)
from tests.unit.application.evaluators.conftest import make_rule as _make_rule


def make_rule(**kwargs):
    kwargs.setdefault("rule_type", "circuit_breaker")
    return _make_rule(**kwargs)


async def test_quarantine_flag_present_is_matched() -> None:
    cache = FakeCacheRepository()
    await cache.set("quarantine:anna", "1")
    evaluator = CircuitBreakerEvaluator(cache)
    rule = make_rule()
    policy = make_policy()
    ctx = make_context(identity=make_identity(sub="anna"))

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.reason == "User quarantined after repeated blocked actions"


async def test_no_quarantine_flag_is_not_matched() -> None:
    cache = FakeCacheRepository()
    evaluator = CircuitBreakerEvaluator(cache)
    rule = make_rule()
    policy = make_policy()
    ctx = make_context(identity=make_identity(sub="anna"))

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_evaluator_never_increments_the_counter() -> None:
    cache = FakeCacheRepository()
    evaluator = CircuitBreakerEvaluator(cache)
    rule = make_rule()
    policy = make_policy()
    ctx = make_context(identity=make_identity(sub="anna"))

    await evaluator.evaluate(rule, ctx, policy)
    await evaluator.evaluate(rule, ctx, policy)

    assert cache.store == {}


async def test_missing_identity_is_not_matched() -> None:
    cache = FakeCacheRepository()
    evaluator = CircuitBreakerEvaluator(cache)
    rule = make_rule()
    policy = make_policy()
    ctx = make_context(no_identity=True)

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False
