from __future__ import annotations

from typing import Protocol

from control_layer.domain.models.tool import ToolCallRequest, ToolCallResult, ToolDescriptor


class McpGateway(Protocol):
    async def list_tools(self) -> list[ToolDescriptor]: ...

    async def call_tool(self, request: ToolCallRequest) -> ToolCallResult: ...
