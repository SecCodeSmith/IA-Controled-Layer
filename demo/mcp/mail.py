"""Fake mail MCP demo server.

Tools: send. Never actually sends anything; always returns a confirmation.
"""

from typing import Any

from demo.mcp.common import ascii_safe, create_server

mcp = create_server("mail", "Fake mail server for the AI Control Layer demo.")


@mcp.tool()
@ascii_safe
def send(to: str, subject: str, body: str) -> dict[str, Any]:
    """Send an email (simulated: nothing is actually sent)."""
    return {"sent": True, "to": to}


if __name__ == "__main__":
    mcp.run()
