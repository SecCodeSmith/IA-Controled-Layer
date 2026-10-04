from __future__ import annotations

import pytest

from control_layer.application.evaluators.authorization.resource_scope import (
    ResourceScopeEvaluator,
)
from control_layer.domain.models.enums import InterceptionPoint, Role
from control_layer.domain.models.resource import PathScope, ResourceConfig, ResourceGrant
from tests.unit.application.evaluators.conftest import (
    make_context,
    make_identity,
    make_policy,
    make_rule,
    make_tool_call,
)

_RESOURCE = ResourceConfig(
    id="github_repo_files",
    server="github",
    tools=["read_file"],
    path_argument="path",
    roles={"developer": ResourceGrant(paths=PathScope(allow=["src/**"], deny=["**/.env"]))},
)


def _policy():
    return make_policy().model_copy(update={"resources": [_RESOURCE]})


def _rule():
    return make_rule(rule_id="resource_scope", rule_type="resource_scope")


def _ctx(path: str | None, role: Role = Role.developer, tool: str = "read_file", **kwargs):
    arguments = {"repo": "web-app"}
    if path is not None:
        arguments["path"] = path
    return make_context(
        identity=make_identity(role=role),
        point=kwargs.pop("point", InterceptionPoint.tool_call),
        tool_call=make_tool_call(server="github", tool=tool, arguments=arguments),
    )


@pytest.mark.asyncio
async def test_allowed_path_is_not_matched() -> None:
    outcome = await ResourceScopeEvaluator().evaluate(_rule(), _ctx("src/app.py"), _policy())

    assert outcome.matched is False


@pytest.mark.asyncio
async def test_denied_path_is_matched_with_pattern_evidence() -> None:
    outcome = await ResourceScopeEvaluator().evaluate(_rule(), _ctx("src/.env"), _policy())

    assert outcome.matched is True
    assert outcome.reason == "denied by pattern **/.env"
    assert outcome.evidence == ["resource:github_repo_files", "pattern:**/.env"]


@pytest.mark.asyncio
async def test_path_outside_allow_list_has_resource_evidence_only() -> None:
    outcome = await ResourceScopeEvaluator().evaluate(_rule(), _ctx("README.md"), _policy())

    assert outcome.matched is True
    assert outcome.reason == "not in allow list"
    assert outcome.evidence == ["resource:github_repo_files"]


@pytest.mark.asyncio
async def test_missing_path_argument_is_matched() -> None:
    outcome = await ResourceScopeEvaluator().evaluate(_rule(), _ctx(None), _policy())

    assert outcome.matched is True
    assert outcome.reason == "missing path argument 'path'"


@pytest.mark.asyncio
async def test_role_without_grant_is_matched() -> None:
    ctx = _ctx("src/app.py", role=Role.finance)

    outcome = await ResourceScopeEvaluator().evaluate(_rule(), ctx, _policy())

    assert outcome.matched is True
    assert outcome.reason == "no resource grant for role 'finance'"
    assert outcome.evidence == ["resource:github_repo_files"]


@pytest.mark.asyncio
async def test_uncovered_tool_is_not_matched() -> None:
    ctx = _ctx("src/.env", tool="list_branches")

    outcome = await ResourceScopeEvaluator().evaluate(_rule(), ctx, _policy())

    assert outcome.matched is False


@pytest.mark.asyncio
async def test_policy_without_resources_is_not_matched() -> None:
    outcome = await ResourceScopeEvaluator().evaluate(_rule(), _ctx("src/.env"), make_policy())

    assert outcome.matched is False


@pytest.mark.asyncio
async def test_other_interception_points_are_ignored() -> None:
    ctx = _ctx("src/.env", point=InterceptionPoint.tool_result)

    outcome = await ResourceScopeEvaluator().evaluate(_rule(), ctx, _policy())

    assert outcome.matched is False


@pytest.mark.asyncio
async def test_context_without_tool_call_or_identity_is_ignored() -> None:
    evaluator = ResourceScopeEvaluator()
    without_call = make_context(point=InterceptionPoint.tool_call)
    without_identity = make_context(
        point=InterceptionPoint.tool_call,
        no_identity=True,
        tool_call=make_tool_call(server="github", tool="read_file", arguments={"path": "src/.env"}),
    )

    assert (await evaluator.evaluate(_rule(), without_call, _policy())).matched is False
    assert (await evaluator.evaluate(_rule(), without_identity, _policy())).matched is False
