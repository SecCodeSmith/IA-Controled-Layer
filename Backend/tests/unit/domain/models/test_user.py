import pytest
from pydantic import ValidationError

from control_layer.domain.models.enums import Role
from control_layer.domain.models.user import DemoUser


def test_demo_user_coerces_role_string_to_enum() -> None:
    user = DemoUser(
        sub="anna.kowalska",
        name="Anna Kowalska",
        initials="AK",
        role="developer",
        location="Krakow, PL",
        region="PL",
        agent_id="agent-anna-dev-7f3a",
        mcp_servers=["github", "ci"],
    )
    assert user.role == Role.developer
    assert user.mcp_servers == ["github", "ci"]


def test_demo_user_mcp_servers_defaults_to_empty_list() -> None:
    user = DemoUser(
        sub="marek.nowak",
        name="Marek Nowak",
        initials="MN",
        role=Role.hr,
        location="Warsaw, PL",
        region="PL",
        agent_id="agent-marek-hr",
    )
    assert user.mcp_servers == []


def test_demo_user_is_frozen() -> None:
    user = DemoUser(
        sub="marek.nowak",
        name="Marek Nowak",
        initials="MN",
        role=Role.hr,
        location="Warsaw, PL",
        region="PL",
        agent_id="agent-marek-hr",
    )
    with pytest.raises(ValidationError):
        user.name = "Someone Else"
