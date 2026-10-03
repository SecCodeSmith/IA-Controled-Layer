"""Fake Jira MCP demo server.

Tools: search.
"""

from typing import Any

from demo.mcp import data
from demo.mcp.common import ascii_safe, create_server

mcp = create_server("jira", "Fake Jira server for the AI Control Layer demo.")


@mcp.tool()
@ascii_safe
def search(query: str) -> dict[str, Any]:
    """Search tickets by a text query matched against key and title."""
    needle = query.lower()
    matches = [
        ticket
        for ticket in data.JIRA_TICKETS
        if needle in ticket["key"].lower() or needle in ticket["title"].lower()
    ]
    return {"query": query, "tickets": matches}


if __name__ == "__main__":
    mcp.run()
