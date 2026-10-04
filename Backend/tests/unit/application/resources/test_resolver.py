from __future__ import annotations

from control_layer.application.resources.resolver import find_grant
from control_layer.domain.models.resource import ColumnScope, ResourceConfig, ResourceGrant
from tests.unit.application.evaluators.conftest import make_policy

_HR_GRANT = ResourceGrant(columns=ColumnScope(deny=["salary"]))
_DEFAULT_GRANT = ResourceGrant(columns=ColumnScope(allow=["id"]))


def _policy(*resources: ResourceConfig):
    return make_policy().model_copy(update={"resources": list(resources)})


def _resource(**overrides: object) -> ResourceConfig:
    fields: dict = {
        "id": "r1",
        "server": "hr-db",
        "tools": ["query"],
        "roles": {"hr": _HR_GRANT},
    }
    fields.update(overrides)
    return ResourceConfig(**fields)


def test_no_resources_returns_none() -> None:
    assert find_grant(_policy(), "hr-db", "query", "hr") is None


def test_uncovered_server_returns_none() -> None:
    assert find_grant(_policy(_resource()), "github", "query", "hr") is None


def test_uncovered_tool_returns_none() -> None:
    assert find_grant(_policy(_resource()), "hr-db", "get_employee", "hr") is None


def test_empty_tools_covers_every_tool() -> None:
    match = find_grant(_policy(_resource(tools=[])), "hr-db", "anything", "hr")

    assert match is not None
    assert match.resource.id == "r1"


def test_role_grant_is_returned() -> None:
    match = find_grant(_policy(_resource()), "hr-db", "query", "hr")

    assert match is not None
    assert match.role == "hr"
    assert match.grant == _HR_GRANT


def test_wildcard_grant_is_used_when_role_has_none() -> None:
    resource = _resource(roles={"hr": _HR_GRANT, "*": _DEFAULT_GRANT})

    match = find_grant(_policy(resource), "hr-db", "query", "developer")

    assert match is not None
    assert match.grant == _DEFAULT_GRANT


def test_role_grant_takes_precedence_over_wildcard() -> None:
    resource = _resource(roles={"hr": _HR_GRANT, "*": _DEFAULT_GRANT})

    match = find_grant(_policy(resource), "hr-db", "query", "hr")

    assert match is not None
    assert match.grant == _HR_GRANT


def test_covered_resource_without_applicable_grant_has_none_grant() -> None:
    match = find_grant(_policy(_resource()), "hr-db", "query", "developer")

    assert match is not None
    assert match.grant is None
    assert match.role == "developer"


def test_first_covering_resource_wins() -> None:
    first = _resource(id="first", roles={"hr": _HR_GRANT})
    second = _resource(id="second", roles={"hr": _DEFAULT_GRANT})

    match = find_grant(_policy(first, second), "hr-db", "query", "hr")

    assert match is not None
    assert match.resource.id == "first"
