from control_layer.application.evaluators.behavior.rate_limit import RateLimitEvaluator
from tests.unit.application.evaluators.conftest import (
    FakeCacheRepository,
    make_context,
    make_identity,
    make_policy,
)
from tests.unit.application.evaluators.conftest import make_rule as _make_rule


def make_rule(**kwargs):
    kwargs.setdefault("rule_type", "rate_limit")
    return _make_rule(**kwargs)


async def test_count_within_limit_is_not_matched() -> None:
    cache = FakeCacheRepository()
    evaluator = RateLimitEvaluator(cache)
    rule = make_rule(params={"per_minute": 5})
    policy = make_policy()
    ctx = make_context(identity=make_identity(sub="anna"))

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_count_over_limit_is_matched() -> None:
    cache = FakeCacheRepository()
    evaluator = RateLimitEvaluator(cache)
    rule = make_rule(params={"per_minute": 2})
    policy = make_policy()
    ctx = make_context(identity=make_identity(sub="anna"))

    await evaluator.evaluate(rule, ctx, policy)
    await evaluator.evaluate(rule, ctx, policy)
    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.reason == "Rate limit exceeded"


async def test_counter_uses_ttl_of_120_seconds() -> None:
    cache = FakeCacheRepository()
    evaluator = RateLimitEvaluator(cache)
    rule = make_rule(params={"per_minute": 60})
    policy = make_policy()
    ctx = make_context(identity=make_identity(sub="anna"))

    await evaluator.evaluate(rule, ctx, policy)

    key = next(iter(cache.store))
    assert key.startswith("rate:anna:")
    assert cache.ttls[key] == 120


async def test_different_users_have_independent_counters() -> None:
    cache = FakeCacheRepository()
    evaluator = RateLimitEvaluator(cache)
    rule = make_rule(params={"per_minute": 1})
    policy = make_policy()

    ctx_anna = make_context(identity=make_identity(sub="anna"))
    ctx_marek = make_context(identity=make_identity(sub="marek"))

    await evaluator.evaluate(rule, ctx_anna, policy)
    outcome_marek = await evaluator.evaluate(rule, ctx_marek, policy)

    assert outcome_marek.matched is False


async def test_missing_identity_is_not_matched() -> None:
    cache = FakeCacheRepository()
    evaluator = RateLimitEvaluator(cache)
    rule = make_rule(params={"per_minute": 0})
    policy = make_policy()
    ctx = make_context(no_identity=True)

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_burst_across_a_minute_boundary_is_still_limited() -> None:
    cache = FakeCacheRepository()
    now = 1_000_000.0
    evaluator = RateLimitEvaluator(cache, clock=lambda: now)
    rule = make_rule(params={"per_minute": 4})
    policy = make_policy()
    ctx = make_context(identity=make_identity(sub="anna"))

    for second in (57.0, 58.0, 59.0, 60.0):
        now = 1_000_000.0 + second
        outcome = await evaluator.evaluate(rule, ctx, policy)
        assert outcome.matched is False
    now = 1_000_061.0
    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.evidence == ["5"]


async def test_calls_older_than_the_window_are_forgotten() -> None:
    cache = FakeCacheRepository()
    now = 2_000_000.0
    evaluator = RateLimitEvaluator(cache, clock=lambda: now)
    rule = make_rule(params={"per_minute": 2})
    policy = make_policy()
    ctx = make_context(identity=make_identity(sub="anna"))

    await evaluator.evaluate(rule, ctx, policy)
    await evaluator.evaluate(rule, ctx, policy)
    now = 2_000_070.0
    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False
