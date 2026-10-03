from __future__ import annotations

from control_layer.application.use_cases.list_tools import ListToolsUseCase
from control_layer.domain.models.enums import Role
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.tool import ToolDescriptor


class _FakeToolCatalog:
    def __init__(self, tools: list[ToolDescriptor]) -> None:
        self._tools = tools
        self.calls: list[Identity] = []

    async def provisioned_for(self, identity: Identity) -> list[ToolDescriptor]:
        self.calls.append(identity)
        return self._tools

    async def descriptor(self, server: str, tool: str) -> ToolDescriptor:
        raise NotImplementedError


def _identity() -> Identity:
    return Identity(
        sub="anna.kowalska",
        name="Anna Kowalska",
        role=Role.developer,
        location="Krakow, PL",
        region="PL",
        agent_id="agent-anna-dev-7f3a",
    )


async def test_delegates_to_tool_catalog() -> None:
    descriptor = ToolDescriptor(
        server="github", name="list_branches", qualified_name="github.list_branches",
        description="", input_schema={}, tags=[], scope="read",
    )
    catalog = _FakeToolCatalog([descriptor])
    use_case = ListToolsUseCase(catalog)
    identity = _identity()
    result = await use_case.execute(identity)
    assert result == [descriptor]
    assert catalog.calls == [identity]
