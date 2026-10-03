"""ToolDescriptor <-> OpenAI function-calling spec mapping.

The OpenAI function name has to be a single identifier, so a tool server id
and tool name (e.g. server `logs-db`, tool `query`) are joined with a double
underscore: `logs-db__query`. Hyphens in the server id are kept as-is; the
double underscore is always the separator, which is safe because tool names
only ever contain single underscores (e.g. `list_branches`).
"""

from __future__ import annotations

from demo_agent.schemas import ToolDescriptor

_SEPARATOR = "__"


def to_openai_function_name(server: str, tool: str) -> str:
    return f"{server}{_SEPARATOR}{tool}"


def to_qualified_name(server: str, tool: str) -> str:
    return f"{server}.{tool}"


def parse_function_name(name: str) -> tuple[str, str]:
    server, separator, tool = name.partition(_SEPARATOR)
    if separator != _SEPARATOR or not server or not tool:
        raise ValueError(f"invalid tool function name: {name!r}")
    return server, tool


def tool_descriptor_to_openai_function(descriptor: ToolDescriptor) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": to_openai_function_name(descriptor.server, descriptor.name),
            "description": descriptor.description,
            "parameters": descriptor.input_schema,
        },
    }


def to_openai_tools(descriptors: list[ToolDescriptor]) -> list[dict[str, object]]:
    return [tool_descriptor_to_openai_function(descriptor) for descriptor in descriptors]
