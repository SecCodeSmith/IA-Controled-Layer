from __future__ import annotations

import logging
import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

import yaml
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from control_layer.domain.models.tool import ToolDescriptor

logger = logging.getLogger(__name__)


def load_server_configs(path: Path | str) -> list[dict[str, Any]]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return data.get("servers", [])


def build_tool_descriptor(
    server_name: str,
    tool_name: str,
    description: str | None,
    input_schema: dict[str, Any] | None,
    tools_config: dict[str, Any],
) -> ToolDescriptor:
    tool_cfg = tools_config.get(tool_name) or {}
    tags = list(tool_cfg.get("tags", []))
    scope = "write" if "destructive" in tags else "read"
    return ToolDescriptor(
        server=server_name,
        name=tool_name,
        qualified_name=f"{server_name}.{tool_name}",
        description=description or "",
        input_schema=input_schema or {},
        tags=tags,
        data_region=tool_cfg.get("data_region"),
        scope=scope,
    )


class _ServerHandle:
    def __init__(self, name: str) -> None:
        self.name = name
        self.session: ClientSession | None = None
        self.status: str = "pending"
        self.error: str | None = None
        self.tool_descriptors: list[ToolDescriptor] = []


class McpServerRegistry:
    def __init__(self, config_path: Path | str, base_dir: Path | str) -> None:
        self._config_path = Path(config_path)
        self._base_dir = Path(base_dir)
        self._servers: dict[str, _ServerHandle] = {}
        self._stack = AsyncExitStack()

    async def start(self) -> None:
        for server_cfg in load_server_configs(self._config_path):
            await self._start_server(server_cfg)

    async def _start_server(self, server_cfg: dict[str, Any]) -> None:
        name = server_cfg["name"]
        handle = _ServerHandle(name)
        self._servers[name] = handle
        try:
            env = {**os.environ, **server_cfg.get("env", {})}
            env.setdefault("PYTHONUTF8", "1")
            env.setdefault("PYTHONIOENCODING", "utf-8")

            cwd_cfg = server_cfg.get("cwd")
            resolved_cwd = str((self._base_dir / cwd_cfg).resolve()) if cwd_cfg else None

            params = StdioServerParameters(
                command=server_cfg["command"],
                args=server_cfg.get("args", []),
                env=env,
                cwd=resolved_cwd,
            )
            read, write = await self._stack.enter_async_context(stdio_client(params))
            session = await self._stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            tools_result = await session.list_tools()
            tools_config = server_cfg.get("tools", {})
            descriptors = [
                build_tool_descriptor(
                    name, tool.name, tool.description, tool.inputSchema, tools_config
                )
                for tool in tools_result.tools
            ]

            handle.session = session
            handle.tool_descriptors = descriptors
            handle.status = "connected"
        except Exception as exc:
            handle.status = "failed"
            handle.error = str(exc)
            logger.error("MCP server '%s' failed to start: %s", name, exc)

    async def aclose(self) -> None:
        await self._stack.aclose()

    def session_for(self, server: str) -> ClientSession | None:
        handle = self._servers.get(server)
        return handle.session if handle else None

    def list_tools(self) -> list[ToolDescriptor]:
        result: list[ToolDescriptor] = []
        for handle in self._servers.values():
            result.extend(handle.tool_descriptors)
        return result

    def status(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "status": handle.status,
                "tools": len(handle.tool_descriptors),
                "error": handle.error,
            }
            for name, handle in self._servers.items()
        }
