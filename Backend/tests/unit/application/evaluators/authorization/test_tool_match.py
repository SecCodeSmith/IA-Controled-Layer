from control_layer.application.evaluators.authorization.tool_match import ToolMatchEvaluator
from tests.unit.application.evaluators.conftest import (
    make_context,
    make_descriptor,
    make_policy,
    make_rule,
    make_tool_call,
)


async def test_glob_match_on_tool_name_is_matched() -> None:
    evaluator = ToolMatchEvaluator()
    rule = make_rule(
        rule_type="tool_match", action="block", match={"action": ["delete_*", "push_main"]}
    )
    policy = make_policy()
    ctx = make_context(
        tool_call=make_tool_call(server="github", tool="delete_branch"),
        metadata={"tool_descriptor": make_descriptor(server="github", name="delete_branch")},
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.reason == f"Tool call matches {rule.id}"


async def test_require_approval_action_uses_confirmation_reason() -> None:
    evaluator = ToolMatchEvaluator()
    rule = make_rule(
        rule_type="tool_match", action="require_approval", match={"action": ["delete_*"]}
    )
    policy = make_policy()
    ctx = make_context(
        tool_call=make_tool_call(server="github", tool="delete_branch"),
        metadata={"tool_descriptor": make_descriptor(server="github", name="delete_branch")},
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.reason == "Destructive actions need your confirmation"


async def test_no_glob_match_is_not_matched() -> None:
    evaluator = ToolMatchEvaluator()
    rule = make_rule(rule_type="tool_match", match={"action": ["drop_*"]})
    policy = make_policy()
    ctx = make_context(
        tool_call=make_tool_call(server="github", tool="get_readme"),
        metadata={"tool_descriptor": make_descriptor(server="github", name="get_readme")},
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_server_mismatch_is_not_matched() -> None:
    evaluator = ToolMatchEvaluator()
    rule = make_rule(rule_type="tool_match", match={"action": ["transfer"], "server": "payments"})
    policy = make_policy()
    ctx = make_context(
        tool_call=make_tool_call(server="hr-db", tool="transfer"),
        metadata={"tool_descriptor": make_descriptor(server="hr-db", name="transfer")},
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_args_glob_mismatch_is_not_matched() -> None:
    evaluator = ToolMatchEvaluator()
    rule = make_rule(
        rule_type="tool_match",
        match={"action": ["transfer"], "args": {"beneficiary": "acct-eu-*"}},
    )
    policy = make_policy()
    ctx = make_context(
        tool_call=make_tool_call(
            server="payments", tool="transfer", arguments={"beneficiary": "acct-us-1"}
        ),
        metadata={"tool_descriptor": make_descriptor(server="payments", name="transfer")},
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_args_glob_match_is_matched() -> None:
    evaluator = ToolMatchEvaluator()
    rule = make_rule(
        rule_type="tool_match",
        match={"action": ["transfer"], "args": {"beneficiary": "acct-eu-*"}},
    )
    policy = make_policy()
    ctx = make_context(
        tool_call=make_tool_call(
            server="payments", tool="transfer", arguments={"beneficiary": "acct-eu-1"}
        ),
        metadata={"tool_descriptor": make_descriptor(server="payments", name="transfer")},
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True


async def test_missing_tool_call_is_not_matched() -> None:
    evaluator = ToolMatchEvaluator()
    rule = make_rule(rule_type="tool_match", match={"action": ["delete_*"]})
    policy = make_policy()
    ctx = make_context(metadata={"tool_descriptor": make_descriptor()})

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False
