from control_layer.application.evaluators.behavior.loop_guard import LoopGuardEvaluator
from tests.unit.application.evaluators.conftest import (
    FakeCacheRepository,
    make_context,
    make_policy,
    make_tool_call,
)
from tests.unit.application.evaluators.conftest import make_rule as _make_rule


def make_rule(**kwargs):
    kwargs.setdefault("rule_type", "loop_guard")
    return _make_rule(**kwargs)


async def test_repeated_identical_call_over_threshold_is_matched() -> None:
    cache = FakeCacheRepository()
    evaluator = LoopGuardEvaluator(cache)
    rule = make_rule(params={"identical_calls": 2, "window_s": 60})
    policy = make_policy()
    tool_call = make_tool_call(server="github", tool="get_readme", arguments={"repo": "x"})
    ctx = make_context(session_id="s1", tool_call=tool_call)

    await evaluator.evaluate(rule, ctx, policy)
    await evaluator.evaluate(rule, ctx, policy)
    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.reason == "Repeated identical tool call, possible runaway loop"


async def test_count_within_threshold_is_not_matched() -> None:
    cache = FakeCacheRepository()
    evaluator = LoopGuardEvaluator(cache)
    rule = make_rule(params={"identical_calls": 5, "window_s": 60})
    policy = make_policy()
    tool_call = make_tool_call(server="github", tool="get_readme", arguments={"repo": "x"})
    ctx = make_context(session_id="s1", tool_call=tool_call)

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_different_arguments_use_independent_counters() -> None:
    cache = FakeCacheRepository()
    evaluator = LoopGuardEvaluator(cache)
    rule = make_rule(params={"identical_calls": 1, "window_s": 60})
    policy = make_policy()

    ctx_a = make_context(
        session_id="s1",
        tool_call=make_tool_call(server="github", tool="get_readme", arguments={"repo": "a"}),
    )
    ctx_b = make_context(
        session_id="s1",
        tool_call=make_tool_call(server="github", tool="get_readme", arguments={"repo": "b"}),
    )

    await evaluator.evaluate(rule, ctx_a, policy)
    outcome_b = await evaluator.evaluate(rule, ctx_b, policy)

    assert outcome_b.matched is False


async def test_different_sessions_use_independent_counters() -> None:
    cache = FakeCacheRepository()
    evaluator = LoopGuardEvaluator(cache)
    rule = make_rule(params={"identical_calls": 1, "window_s": 60})
    policy = make_policy()
    tool_call = make_tool_call(server="github", tool="get_readme", arguments={"repo": "x"})

    ctx_s1 = make_context(session_id="s1", tool_call=tool_call)
    ctx_s2 = make_context(session_id="s2", tool_call=tool_call)

    await evaluator.evaluate(rule, ctx_s1, policy)
    outcome_s2 = await evaluator.evaluate(rule, ctx_s2, policy)

    assert outcome_s2.matched is False


async def test_counter_uses_configured_window_as_ttl() -> None:
    cache = FakeCacheRepository()
    evaluator = LoopGuardEvaluator(cache)
    rule = make_rule(params={"identical_calls": 5, "window_s": 45})
    policy = make_policy()
    tool_call = make_tool_call(server="github", tool="get_readme", arguments={"repo": "x"})
    ctx = make_context(session_id="s1", tool_call=tool_call)

    await evaluator.evaluate(rule, ctx, policy)

    key = next(iter(cache.store))
    assert key.startswith("loop:s1:")
    assert cache.ttls[key] == 45


async def test_missing_tool_call_is_not_matched() -> None:
    cache = FakeCacheRepository()
    evaluator = LoopGuardEvaluator(cache)
    rule = make_rule(params={"identical_calls": 0})
    policy = make_policy()
    ctx = make_context(session_id="s1")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False
