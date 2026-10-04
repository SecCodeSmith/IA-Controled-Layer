from __future__ import annotations

import pytest
from pydantic import ValidationError

from control_layer.domain.models.resource import (
    WILDCARD_ROLE,
    ColumnScope,
    PathDecision,
    PathScope,
    ProjectionResult,
    ResourceConfig,
    ResourceGrant,
    ResourceMatch,
)


def _config(**overrides: object) -> ResourceConfig:
    data: dict = {"id": "files", "server": "github"}
    data.update(overrides)
    return ResourceConfig.model_validate(data)


def test_grant_defaults_place_no_restriction() -> None:
    grant = ResourceGrant()

    assert grant.paths == PathScope(allow=[], deny=[])
    assert grant.columns == ColumnScope(allow=None, deny=[])
    assert grant.rows == {}


def test_grant_rows_accept_scalar_and_list_values() -> None:
    grant = ResourceGrant(rows={"region": "$identity.region", "team": ["a", "b"]})

    assert grant.rows == {"region": "$identity.region", "team": ["a", "b"]}


def test_column_scope_distinguishes_empty_allow_from_unrestricted() -> None:
    assert ColumnScope().allow is None
    assert ColumnScope(allow=[]).allow == []


def test_resource_config_defaults() -> None:
    config = _config()

    assert config.tools == []
    assert config.path_argument is None
    assert config.records is None
    assert config.roles == {}


def test_resource_config_parses_nested_grants() -> None:
    config = _config(
        tools=["read_file"],
        path_argument="path",
        roles={"developer": {"paths": {"allow": ["src/**"], "deny": ["**/.env"]}}},
    )

    grant = config.roles["developer"]
    assert grant.paths.allow == ["src/**"]
    assert grant.paths.deny == ["**/.env"]


def test_resource_config_accepts_every_role_and_wildcard() -> None:
    config = _config(roles={"developer": {}, "hr": {}, "finance": {}, WILDCARD_ROLE: {}})

    assert set(config.roles) == {"developer", "hr", "finance", "*"}


def test_resource_config_rejects_unknown_role_key() -> None:
    with pytest.raises(ValidationError):
        _config(roles={"ceo": {}})


def test_resource_config_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        _config(tool=["read_file"])


def test_grant_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ResourceGrant.model_validate({"colums": {"deny": ["salary"]}})


def test_resource_config_without_tools_covers_every_tool_on_its_server() -> None:
    config = _config()

    assert config.covers("github", "read_file")
    assert config.covers("github", "anything")
    assert not config.covers("hr-db", "read_file")


def test_resource_config_with_tools_covers_only_listed_tools() -> None:
    config = _config(tools=["read_file"])

    assert config.covers("github", "read_file")
    assert not config.covers("github", "push_main")


def test_resource_models_are_frozen() -> None:
    config = _config()

    with pytest.raises(ValidationError):
        config.server = "other"  # type: ignore[misc]


def test_path_decision_shape() -> None:
    decision = PathDecision(
        allowed=False, path="secrets/x.pem", pattern="secrets/**", reason="denied"
    )

    assert decision.allowed is False
    assert decision.pattern == "secrets/**"


def test_projection_result_defaults_to_unchanged() -> None:
    result = ProjectionResult(data={"rows": []})

    assert result.rows_filtered == 0
    assert result.columns_redacted == []
    assert result.changed is False


def test_resource_match_carries_optional_grant() -> None:
    match = ResourceMatch(resource=_config(), role="hr", grant=None)

    assert match.grant is None
    assert match.resource.id == "files"
