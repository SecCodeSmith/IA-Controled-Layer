from __future__ import annotations

from control_layer.application.services.tool_catalog import ProvisionedTool
from control_layer.application.use_cases.list_tools import ListToolsUseCase
from control_layer.domain.models.enums import Role
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.tool import ToolDescriptor


class _FakeToolCatalog:
    def __init__(self, tools: list[ProvisionedTool]) -> None:
        self._tools = tools

    async def all_tools(self, identity: Identity) -> list[ProvisionedTool]:
        return self._tools


def _identity() -> Identity:
    return Identity(
        sub="anna.kowalska",
        name="Anna Kowalska",
        role=Role.developer,
        location="Krakow, PL",
        region="PL",
        agent_id="agent-anna-dev-7f3a",
    )


def _tool(name: str, provisioned: bool) -> ProvisionedTool:
    return ProvisionedTool(
        descriptor=ToolDescriptor(
            server="github",
            name=name,
            qualified_name=f"github.{name}",
            description="",
            input_schema={},
            tags=[],
            scope="read",
        ),
        provisioned=provisioned,
    )


async def test_provisioned_scope_returns_only_provisioned_tools() -> None:
    tools = [_tool("a", True), _tool("b", False)]
    result = await ListToolsUseCase(_FakeToolCatalog(tools)).execute(_identity())
    assert [t.descriptor.name for t in result] == ["a"]


async def test_all_scope_returns_everything_flagged() -> None:
    tools = [_tool("a", True), _tool("b", False)]
    result = await ListToolsUseCase(_FakeToolCatalog(tools)).execute(_identity(), scope="all")
    assert [(t.descriptor.name, t.provisioned) for t in result] == [("a", True), ("b", False)]
