"""Shared helpers for the demo MCP servers.

Every demo server is a tiny `FastMCP` stdio process. This module provides:

- `create_server`: a thin factory so every module constructs its `FastMCP`
  instance the same way.
- `ascii_safe`: a decorator that enforces the "ASCII-only output" rule for
  tool results. Windows stdio consoles in this demo run under cp1252, which
  breaks on non-ASCII bytes; every fake-data string the servers return must
  therefore be plain ASCII (the handful of intentionally attacker-controlled
  strings, such as the vendor-sdk README injection, are also plain ASCII).
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP


def create_server(name: str, instructions: str | None = None) -> FastMCP:
    """Build a FastMCP server instance for a demo tool server."""
    return FastMCP(name=name, instructions=instructions)


def ensure_ascii(value: Any, path: str = "result") -> None:
    """Raise ValueError if any string nested in `value` is not ASCII."""
    if isinstance(value, str):
        if not value.isascii():
            raise ValueError(f"non-ASCII content in {path}: {value!r}")
        return
    if isinstance(value, dict):
        for key, inner in value.items():
            ensure_ascii(key, f"{path}.{key}")
            ensure_ascii(inner, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, inner in enumerate(value):
            ensure_ascii(inner, f"{path}[{index}]")
        return
    # numbers, bools, None: nothing to check


def ascii_safe[F: Callable[..., Any]](fn: F) -> F:
    """Decorator: validate a tool's return value is ASCII-only before it ships."""
    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await fn(*args, **kwargs)
            ensure_ascii(result, fn.__name__)
            return result

        return async_wrapper  # type: ignore[return-value]

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = fn(*args, **kwargs)
        ensure_ascii(result, fn.__name__)
        return result

    return wrapper  # type: ignore[return-value]
