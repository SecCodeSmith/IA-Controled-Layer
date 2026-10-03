from __future__ import annotations

from control_layer.application.services.tool_catalog import ToolCatalog
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.tool import ToolDescriptor


class ListToolsUseCase:
    def __init__(self, tool_catalog: ToolCatalog) -> None:
        self._tool_catalog = tool_catalog

    async def execute(self, identity: Identity) -> list[ToolDescriptor]:
        return await self._tool_catalog.provisioned_for(identity)
