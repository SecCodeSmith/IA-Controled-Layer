"""Fake EU customers MCP demo server.

Tools: read. Tagged with `data_region: eu_customers` in mcp_servers.yaml so
the control layer can enforce residency rules (allowed regions PL/DE/FR).
"""

from typing import Any

from demo.mcp import data
from demo.mcp.common import ascii_safe, create_server

mcp = create_server("eu-customers", "Fake EU customers server for the AI Control Layer demo.")


@mcp.tool()
@ascii_safe
def read(customer_id: str) -> dict[str, Any]:
    """Read an EU customer record by customer id."""
    record = data.EU_CUSTOMERS.get(customer_id)
    if record is None:
        return {"customer_id": customer_id, "found": False}
    return {"found": True, **record}


if __name__ == "__main__":
    mcp.run()
