from __future__ import annotations

import pytest

from control_layer.application.services.tool_catalog import ToolCatalog
from control_layer.domain.exceptions import UnknownToolError
from control_layer.domain.models.enums import Role
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.tool import ToolDescriptor
from control_layer.domain.policy.parser import parse_policy_document


class _FakeMcpGateway:
    def __init__(self, descriptors: list[ToolDescriptor]) -> None:
        self._descriptors = descriptors

    async def list_tools(self) -> list[ToolDescriptor]:
        return self._descriptors

    async def call_tool(self, request):  # noqa: ANN001, ANN201
        raise NotImplementedError


class _FakePolicyRepository:
    def __init__(self, policy) -> None:  # noqa: ANN001
        self._policy = policy

    async def current(self):  # noqa: ANN201
        return self._policy

    async def reload(self):  # noqa: ANN201
        return self._policy

    async def status(self) -> dict:
        return {}


def _descriptor(server: str, name: str, data_region: str | None = None) -> ToolDescriptor:
    return ToolDescriptor(
        server=server,
        name=name,
        qualified_name=f"{server}.{name}",
        description="",
        input_schema={},
        tags=[],
        data_region=data_region,
        scope="read",
    )


def _policy():
    data = {
        "version": 1,
        "profile": "balanced",
        "models": {"allowed": ["mock"], "pricing": {}},
        "roles": {
            "developer": {"mcp_servers": ["github", "ci"], "tools_deny": ["github.delete_branch"]},
        },
        "locations": {"eu_customers": {"allowed_regions": ["PL", "DE", "FR"]}},
        "rules": [],
        "budgets": {
            "per_user_tokens": 1000,
            "per_user_cost_usd": 1.0,
            "max_tokens_per_request": 100,
            "upstream_timeout_s": 30,
            "warn_at_percent": 80,
            "on_exceeded": "block",
        },
    }
    return parse_policy_document(data, source_hash="h")


def _identity(role: Role = Role.developer, region: str = "PL") -> Identity:
    return Identity(
        sub="anna.kowalska",
        name="Anna Kowalska",
        role=role,
        location="Krakow, PL",
        region=region,
        agent_id="agent-anna-dev-7f3a",
    )


async def test_filters_by_role_mcp_servers() -> None:
    descriptors = [_descriptor("github", "list_branches"), _descriptor("hr-db", "query")]
    catalog = ToolCatalog(_FakeMcpGateway(descriptors), _FakePolicyRepository(_policy()))
    tools = await catalog.provisioned_for(_identity())
    assert [t.qualified_name for t in tools] == ["github.list_branches"]


async def test_filters_out_tools_deny() -> None:
    descriptors = [_descriptor("github", "list_branches"), _descriptor("github", "delete_branch")]
    catalog = ToolCatalog(_FakeMcpGateway(descriptors), _FakePolicyRepository(_policy()))
    tools = await catalog.provisioned_for(_identity())
    assert [t.qualified_name for t in tools] == ["github.list_branches"]


async def test_filters_by_data_region() -> None:
    descriptors = [
        _descriptor("ci", "get_run"),
        _descriptor("ci", "eu_report", data_region="eu_customers"),
    ]
    catalog = ToolCatalog(_FakeMcpGateway(descriptors), _FakePolicyRepository(_policy()))
    us_tools = await catalog.provisioned_for(_identity(region="US"))
    assert [t.name for t in us_tools] == ["get_run"]
    pl_tools = await catalog.provisioned_for(_identity(region="PL"))
    assert {t.name for t in pl_tools} == {"get_run", "eu_report"}


async def test_descriptor_returns_matching_tool() -> None:
    descriptors = [_descriptor("github", "list_branches")]
    catalog = ToolCatalog(_FakeMcpGateway(descriptors), _FakePolicyRepository(_policy()))
    found = await catalog.descriptor("github", "list_branches")
    assert found.qualified_name == "github.list_branches"


async def test_descriptor_raises_unknown_tool_error() -> None:
    catalog = ToolCatalog(_FakeMcpGateway([]), _FakePolicyRepository(_policy()))
    with pytest.raises(UnknownToolError):
        await catalog.descriptor("github", "nonexistent")
