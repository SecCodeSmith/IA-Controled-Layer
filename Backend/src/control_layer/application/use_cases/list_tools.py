from __future__ import annotations

from control_layer.application.services.tool_catalog import ProvisionedTool, ToolCatalog
from control_layer.domain.models.identity import Identity


class ListToolsUseCase:
    def __init__(self, tool_catalog: ToolCatalog) -> None:
        self._tool_catalog = tool_catalog

    async def execute(
        self, identity: Identity, scope: str = "provisioned"
    ) -> list[ProvisionedTool]:
        tools = await self._tool_catalog.all_tools(identity)
        if scope == "all":
            return tools
        return [tool for tool in tools if tool.provisioned]
