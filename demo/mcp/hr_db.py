"""Fake HR database MCP demo server.

Tools: find_approver, get_employee, query.
`get_employee("E-1042")` returns a record containing a checksum-valid PESEL
and an email address, used by the DLP PII-masking demo scenario.
"""

from typing import Any

from demo.mcp import data
from demo.mcp.common import ascii_safe, create_server

mcp = create_server("hr-db", "Fake HR database server for the AI Control Layer demo.")


@mcp.tool()
@ascii_safe
def find_approver(request: str) -> dict[str, Any]:
    """Find the approver responsible for a type of request."""
    approver = data.HR_APPROVERS.get(request, data.HR_DEFAULT_APPROVER)
    return {"request": request, **approver}


@mcp.tool()
@ascii_safe
def get_employee(employee_id: str) -> dict[str, Any]:
    """Get an employee record by employee id."""
    employee = data.HR_EMPLOYEES.get(employee_id)
    if employee is None:
        return {"employee_id": employee_id, "found": False}
    return {"found": True, **employee}


@mcp.tool()
@ascii_safe
def query(sql_like: str) -> dict[str, Any]:
    """Run a simplified, read-only query over the employee directory."""
    return {"query": sql_like, "rows": data.HR_QUERY_ROWS}


if __name__ == "__main__":
    mcp.run()
