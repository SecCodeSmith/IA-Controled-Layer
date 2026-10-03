from __future__ import annotations

from mcp.types import CallToolResult, TextContent

from control_layer.domain.models.tool import ToolCallRequest, ToolDescriptor
from control_layer.infrastructure.mcp.mcp_client_gateway import McpClientGateway


class _FakeSession:
    def __init__(self, result: CallToolResult) -> None:
        self.result = result
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name: str, arguments: dict) -> CallToolResult:
        self.calls.append((name, arguments))
        return self.result


class _FakeRegistry:
    def __init__(self, sessions: dict[str, _FakeSession], tools: list[ToolDescriptor]) -> None:
        self._sessions = sessions
        self._tools = tools

    def session_for(self, server: str) -> _FakeSession | None:
        return self._sessions.get(server)

    def list_tools(self) -> list[ToolDescriptor]:
        return self._tools


def _descriptor(server: str, name: str) -> ToolDescriptor:
    return ToolDescriptor(
        server=server,
        name=name,
        qualified_name=f"{server}.{name}",
        description="",
        input_schema={},
        tags=[],
        scope="read",
    )


async def test_list_tools_delegates_to_registry() -> None:
    tools = [_descriptor("ci", "get_run")]
    gateway = McpClientGateway(_FakeRegistry({}, tools))

    result = await gateway.list_tools()

    assert result == tools


async def test_call_tool_prefers_structured_content() -> None:
    result = CallToolResult(
        content=[TextContent(type="text", text="ignored text")],
        structuredContent={"status": "FAILED", "run": "e2e-login"},
        isError=False,
    )
    session = _FakeSession(result)
    gateway = McpClientGateway(_FakeRegistry({"ci": session}, []))

    call_result = await gateway.call_tool(
        ToolCallRequest(server="ci", tool="get_run", arguments={"pipeline": "e2e-login"})
    )

    assert call_result.structured_content == {"status": "FAILED", "run": "e2e-login"}
    assert "FAILED" in call_result.content_text
    assert call_result.is_error is False
    assert session.calls == [("get_run", {"pipeline": "e2e-login"})]


async def test_call_tool_falls_back_to_joined_text_blocks() -> None:
    result = CallToolResult(
        content=[
            TextContent(type="text", text="line one"),
            TextContent(type="text", text="line two"),
        ],
        structuredContent=None,
        isError=False,
    )
    session = _FakeSession(result)
    gateway = McpClientGateway(_FakeRegistry({"logs-db": session}, []))

    call_result = await gateway.call_tool(
        ToolCallRequest(server="logs-db", tool="query", arguments={})
    )

    assert call_result.structured_content is None
    assert call_result.content_text == "line one\nline two"


async def test_call_tool_propagates_is_error() -> None:
    result = CallToolResult(
        content=[TextContent(type="text", text="boom")],
        structuredContent=None,
        isError=True,
    )
    session = _FakeSession(result)
    gateway = McpClientGateway(_FakeRegistry({"github": session}, []))

    call_result = await gateway.call_tool(
        ToolCallRequest(server="github", tool="delete_branch", arguments={})
    )

    assert call_result.is_error is True


async def test_call_tool_unavailable_server_returns_error_result() -> None:
    gateway = McpClientGateway(_FakeRegistry({}, []))

    call_result = await gateway.call_tool(
        ToolCallRequest(server="unknown", tool="whatever", arguments={})
    )

    assert call_result.is_error is True
    assert "unknown" in call_result.content_text
