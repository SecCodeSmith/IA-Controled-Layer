from __future__ import annotations

from control_layer.application.resources.scope_checker import ResourceScopeChecker, ScopeVerdict
from control_layer.domain.models.enums import Role
from control_layer.domain.models.resource import PathScope, ResourceConfig, ResourceGrant
from tests.unit.application.evaluators.conftest import make_identity, make_policy

_GITHUB = ResourceConfig(
    id="github_repo_files",
    server="github",
    tools=["read_file"],
    path_argument="path",
    roles={"developer": ResourceGrant(paths=PathScope(allow=["src/**"], deny=["**/.env"]))},
)
_HR_ROWS = ResourceConfig(
    id="hr_rows", server="hr-db", tools=["query"], roles={"hr": ResourceGrant()}
)
_NO_PATH_ARGUMENT = ResourceConfig(
    id="open", server="ci", roles={"developer": ResourceGrant(paths=PathScope(deny=["*"]))}
)


def _policy():
    return make_policy().model_copy(update={"resources": [_GITHUB, _HR_ROWS, _NO_PATH_ARGUMENT]})


def _check(server: str, tool: str, arguments: dict, role: Role = Role.developer) -> ScopeVerdict:
    return ResourceScopeChecker().check_call(
        _policy(), make_identity(role=role), server, tool, arguments
    )


def test_uncovered_call_is_allowed_without_resource() -> None:
    verdict = _check("logs-db", "query", {})

    assert verdict == ScopeVerdict(
        allowed=True, rule_reason=None, pattern=None, matched_resource_id=None
    )


def test_role_without_grant_is_blocked() -> None:
    verdict = _check("hr-db", "query", {}, role=Role.developer)

    assert verdict.allowed is False
    assert verdict.rule_reason == "no resource grant for role 'developer'"
    assert verdict.matched_resource_id == "hr_rows"
    assert verdict.pattern is None


def test_missing_path_argument_is_blocked() -> None:
    verdict = _check("github", "read_file", {"repo": "web-app"})

    assert verdict.allowed is False
    assert verdict.rule_reason == "missing path argument 'path'"
    assert verdict.matched_resource_id == "github_repo_files"


def test_non_string_path_argument_is_treated_as_missing() -> None:
    verdict = _check("github", "read_file", {"path": 42})

    assert verdict.allowed is False
    assert verdict.rule_reason == "missing path argument 'path'"


def test_allowed_path_is_allowed_with_resource_id() -> None:
    verdict = _check("github", "read_file", {"path": "src/app.py"})

    assert verdict.allowed is True
    assert verdict.rule_reason is None
    assert verdict.matched_resource_id == "github_repo_files"


def test_denied_path_reports_pattern_and_reason() -> None:
    verdict = _check("github", "read_file", {"path": "src/.env"})

    assert verdict.allowed is False
    assert verdict.rule_reason == "denied by pattern **/.env"
    assert verdict.pattern == "**/.env"


def test_path_outside_allow_list_is_blocked() -> None:
    verdict = _check("github", "read_file", {"path": "secrets/deploy.pem"})

    assert verdict.allowed is False
    assert verdict.rule_reason == "not in allow list"


def test_traversal_is_blocked() -> None:
    verdict = _check("github", "read_file", {"path": "src/../.env"})

    assert verdict.allowed is False
    assert verdict.rule_reason == "absolute or traversal path"


def test_resource_without_path_argument_does_not_check_paths() -> None:
    verdict = _check("ci", "get_run", {"path": "anything"})

    assert verdict.allowed is True
    assert verdict.matched_resource_id == "open"
