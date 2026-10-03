"""Fake calendar MCP demo server.

Tools: list.
"""

from typing import Any

from demo.mcp import data
from demo.mcp.common import ascii_safe, create_server

mcp = create_server("calendar", "Fake calendar server for the AI Control Layer demo.")


@mcp.tool(name="list")
@ascii_safe
def list_events(user: str, days: int = 7) -> dict[str, Any]:
    """List upcoming events for a user over the next N days."""
    events = data.CALENDAR_EVENTS.get(user, data.CALENDAR_DEFAULT_EVENTS)
    return {"user": user, "days": days, "events": events}


if __name__ == "__main__":
    mcp.run()
