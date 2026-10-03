import pytest

from control_layer.application.evaluators.authorization.rbac import RbacEvaluator
from control_layer.domain.models.enums import Role
from tests.unit.application.evaluators.conftest import (
    make_context,
    make_descriptor,
    make_identity,
    make_policy,
    make_rule,
)


@pytest.mark.asyncio
async def test_server_provisioned_for_role_is_not_matched() -> None:
    evaluator = RbacEvaluator()
    rule = make_rule(rule_type="rbac")
    policy = make_policy()
    ctx = make_context(
        identity=make_identity(role=Role.developer),
        metadata={"tool_descriptor": make_descriptor(server="github", name="get_readme")},
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


@pytest.mark.asyncio
async def test_server_not_provisioned_is_matched_with_reason() -> None:
    evaluator = RbacEvaluator()
    rule = make_rule(rule_type="rbac")
    policy = make_policy()
    ctx = make_context(
        identity=make_identity(role=Role.developer),
        metadata={"tool_descriptor": make_descriptor(server="hr-db", name="get_employee")},
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.reason == "hr-db is not provisioned for the Developer role"


@pytest.mark.asyncio
async def test_hr_role_label_is_rendered_as_acronym() -> None:
    evaluator = RbacEvaluator()
    rule = make_rule(rule_type="rbac")
    policy = make_policy()
    ctx = make_context(
        identity=make_identity(role=Role.hr),
        metadata={"tool_descriptor": make_descriptor(server="github", name="get_readme")},
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.reason == "github is not provisioned for the HR role"


@pytest.mark.asyncio
async def test_finance_role_label_is_title_cased() -> None:
    evaluator = RbacEvaluator()
    rule = make_rule(rule_type="rbac")
    policy = make_policy()
    ctx = make_context(
        identity=make_identity(role=Role.finance),
        metadata={"tool_descriptor": make_descriptor(server="github", name="get_readme")},
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.reason == "github is not provisioned for the Finance role"


@pytest.mark.asyncio
async def test_qualified_name_in_tools_deny_is_matched() -> None:
    evaluator = RbacEvaluator()
    rule = make_rule(rule_type="rbac")
    policy = make_policy(
        roles={"developer": {"mcp_servers": ["github"], "tools_deny": ["github.delete_branch"]}}
    )
    ctx = make_context(
        identity=make_identity(role=Role.developer),
        metadata={"tool_descriptor": make_descriptor(server="github", name="delete_branch")},
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.reason == "github is not provisioned for the Developer role"


@pytest.mark.asyncio
async def test_missing_tool_descriptor_is_not_matched() -> None:
    evaluator = RbacEvaluator()
    rule = make_rule(rule_type="rbac")
    policy = make_policy()
    ctx = make_context(metadata={})

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


@pytest.mark.asyncio
async def test_missing_identity_is_not_matched() -> None:
    evaluator = RbacEvaluator()
    rule = make_rule(rule_type="rbac")
    policy = make_policy()
    ctx = make_context(no_identity=True, metadata={"tool_descriptor": make_descriptor()})

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False
