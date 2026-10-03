from __future__ import annotations

import json
from typing import Any, Protocol

from control_layer.domain.models.tool import ToolCallRequest, ToolCallResult, ToolDescriptor


class _Session(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


class _Registry(Protocol):
    def session_for(self, server: str) -> _Session | None: ...

    def list_tools(self) -> list[ToolDescriptor]: ...


def _joined_text(content: list[Any]) -> str:
    parts = []
    for block in content:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(text)
    return "\n".join(parts)


class McpClientGateway:
    def __init__(self, registry: _Registry) -> None:
        self._registry = registry

    async def list_tools(self) -> list[ToolDescriptor]:
        return self._registry.list_tools()

    async def call_tool(self, request: ToolCallRequest) -> ToolCallResult:
        session = self._registry.session_for(request.server)
        if session is None:
            return ToolCallResult(
                content_text=f"MCP server '{request.server}' is not available",
                structured_content=None,
                is_error=True,
            )

        result = await session.call_tool(request.tool, request.arguments)
        structured = result.structuredContent
        if structured is not None:
            content_text = json.dumps(structured)
        else:
            content_text = _joined_text(result.content)

        return ToolCallResult(
            content_text=content_text,
            structured_content=structured,
            is_error=result.isError,
        )
