from control_layer.application.evaluators.policy.transaction_limit import (
    TransactionLimitEvaluator,
)
from control_layer.domain.models.enums import InterceptionPoint, Role
from tests.unit.application.evaluators.conftest import (
    make_context,
    make_identity,
    make_policy,
    make_tool_call,
)
from tests.unit.application.evaluators.conftest import make_rule as _make_rule


def make_rule(**kwargs):
    kwargs.setdefault("rule_type", "transaction_limit")
    return _make_rule(**kwargs)


async def test_amount_over_limit_is_matched() -> None:
    evaluator = TransactionLimitEvaluator()
    rule = make_rule()
    policy = make_policy(
        roles={"finance": {"mcp_servers": ["payments"], "transaction_limit": 5000}}
    )
    ctx = make_context(
        identity=make_identity(role=Role.finance),
        point=InterceptionPoint.tool_call,
        tool_call=make_tool_call(server="payments", tool="transfer", arguments={"amount": 6000}),
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.reason == "Transfer of 6000 exceeds the 5000 limit"


async def test_amount_within_limit_is_not_matched() -> None:
    evaluator = TransactionLimitEvaluator()
    rule = make_rule()
    policy = make_policy(
        roles={"finance": {"mcp_servers": ["payments"], "transaction_limit": 5000}}
    )
    ctx = make_context(
        identity=make_identity(role=Role.finance),
        point=InterceptionPoint.tool_call,
        tool_call=make_tool_call(server="payments", tool="transfer", arguments={"amount": 100}),
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_beneficiary_not_on_allowlist_is_matched() -> None:
    evaluator = TransactionLimitEvaluator()
    rule = make_rule()
    policy = make_policy(
        roles={
            "finance": {
                "mcp_servers": ["payments"],
                "transaction_limit": 5000,
                "beneficiary_allowlist": ["acct-eu-main"],
            }
        }
    )
    ctx = make_context(
        identity=make_identity(role=Role.finance),
        point=InterceptionPoint.tool_call,
        tool_call=make_tool_call(
            server="payments",
            tool="transfer",
            arguments={"amount": 100, "beneficiary": "acct-unknown"},
        ),
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.reason == "Beneficiary not on the allowlist"


async def test_beneficiary_on_allowlist_is_not_matched() -> None:
    evaluator = TransactionLimitEvaluator()
    rule = make_rule()
    policy = make_policy(
        roles={
            "finance": {
                "mcp_servers": ["payments"],
                "transaction_limit": 5000,
                "beneficiary_allowlist": ["acct-eu-main"],
            }
        }
    )
    ctx = make_context(
        identity=make_identity(role=Role.finance),
        point=InterceptionPoint.tool_call,
        tool_call=make_tool_call(
            server="payments",
            tool="transfer",
            arguments={"amount": 100, "beneficiary": "acct-eu-main"},
        ),
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_empty_allowlist_does_not_restrict_beneficiary() -> None:
    evaluator = TransactionLimitEvaluator()
    rule = make_rule()
    policy = make_policy(
        roles={
            "finance": {
                "mcp_servers": ["payments"],
                "transaction_limit": 5000,
                "beneficiary_allowlist": [],
            }
        }
    )
    ctx = make_context(
        identity=make_identity(role=Role.finance),
        point=InterceptionPoint.tool_call,
        tool_call=make_tool_call(
            server="payments",
            tool="transfer",
            arguments={"amount": 100, "beneficiary": "acct-anything"},
        ),
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_different_tool_is_not_matched() -> None:
    evaluator = TransactionLimitEvaluator()
    rule = make_rule()
    policy = make_policy(
        roles={"finance": {"mcp_servers": ["payments"], "transaction_limit": 5000}}
    )
    ctx = make_context(
        identity=make_identity(role=Role.finance),
        point=InterceptionPoint.tool_call,
        tool_call=make_tool_call(
            server="payments", tool="get_balance", arguments={"amount": 999999}
        ),
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_custom_tool_param_is_respected() -> None:
    evaluator = TransactionLimitEvaluator()
    rule = make_rule(params={"tool": "hr-db.payout"})
    policy = make_policy(
        roles={"finance": {"mcp_servers": ["payments"], "transaction_limit": 100}}
    )
    ctx = make_context(
        identity=make_identity(role=Role.finance),
        point=InterceptionPoint.tool_call,
        tool_call=make_tool_call(server="hr-db", tool="payout", arguments={"amount": 500}),
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True


async def test_non_tool_call_point_is_not_matched() -> None:
    evaluator = TransactionLimitEvaluator()
    rule = make_rule()
    policy = make_policy()
    ctx = make_context(point=InterceptionPoint.prompt)

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False
