"""Fake logs database MCP demo server.

Tools: query.
`query("auth", ...)` returns three error lines carrying three email
addresses, used by the DLP PII-masking demo scenario.
"""

from typing import Any

from demo.mcp import data
from demo.mcp.common import ascii_safe, create_server

mcp = create_server("logs-db", "Fake logs database server for the AI Control Layer demo.")


AUTH_ALIASES = ("auth", "login", "sso")


def _is_auth_service(service: str) -> bool:
    name = service.lower()
    return any(alias in name for alias in AUTH_ALIASES)


@mcp.tool()
@ascii_safe
def query(service: str, since: str, level: str = "error") -> dict[str, Any]:
    """Query recent error log lines. service: auth, payments or web. since: e.g. 24h."""
    if _is_auth_service(service):
        lines = list(data.LOGS_AUTH_ERROR_LINES)
    else:
        lines = list(
            data.LOGS_DEFAULT_LINES.get(service, [data.LOGS_FALLBACK_LINE.format(service=service)])
        )
    return {"service": service, "since": since, "level": level, "lines": lines}


if __name__ == "__main__":
    mcp.run()
