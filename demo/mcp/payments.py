"""Fake payments MCP demo server.

Tools: get_balance, transfer. Account ids are opaque (`ACC-1001`, ...), not
checksum-valid PAN/IBAN; limits are enforced by the control layer, not here.
"""

import uuid
from typing import Any

from demo.mcp import data
from demo.mcp.common import ascii_safe, create_server

mcp = create_server("payments", "Fake payments server for the AI Control Layer demo.")


@mcp.tool()
@ascii_safe
def get_balance(account: str) -> dict[str, Any]:
    """Get the current balance for an account."""
    record = data.PAYMENTS_ACCOUNTS.get(account)
    if record is not None:
        return dict(record)
    return {
        "account": account,
        "balance": data.PAYMENTS_DEFAULT_BALANCE,
        "currency": data.PAYMENTS_DEFAULT_CURRENCY,
    }


@mcp.tool()
@ascii_safe
def transfer(
    from_account: str, to_iban: str, amount: float, currency: str = "PLN"
) -> dict[str, Any]:
    """Transfer funds from an account to a destination IBAN."""
    transaction_id = f"TXN-{uuid.uuid4().hex[:10]}"
    return {"ok": True, "transaction_id": transaction_id}


if __name__ == "__main__":
    mcp.run()
