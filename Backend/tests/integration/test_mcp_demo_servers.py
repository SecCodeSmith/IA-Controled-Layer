"""Stdio smoke tests for the nine demo MCP servers in `demo/mcp/`.

Each server is spawned as a real subprocess over stdio (no imports of
`demo.mcp.*` into this process), exactly as the control layer's MCP gateway
will spawn them. For every server this asserts `list_tools()` returns the
contracted tool names and one representative `call_tool` returns the
expected content, including the three attack-bearing fixtures used by the
demo (logs-db emails, hr-db PESEL, github vendor-sdk prompt injection).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO_ROOT = Path(__file__).resolve().parents[3]

# Exact three log lines the logs-db fixture returns for service "auth"
# (demo/mcp/data.py: LOGS_AUTH_ERROR_LINES) -- the DLP masking demo expects
# precisely these three emails.
EXPECTED_AUTH_LOG_LINES = [
    "02:11:04 401 invalid_token user=t.lis@example.com",
    "02:11:09 401 invalid_token user=qa.bot@example.com",
    "02:13:30 500 key_not_found ops=k.wrona@example.com",
]

# Checksum-valid PESEL on the hr-db E-1042 fixture (demo/mcp/data.py:
# HR_EMPLOYEES) used by the DLP masking demo.
EXPECTED_PESEL = "44051401359"


@dataclass(frozen=True)
class ServerCase:
    module: str
    expected_tools: frozenset[str]
    tool_name: str
    arguments: dict[str, Any]
    check: Callable[[dict[str, Any]], None]


def _check_github_readme(result: dict[str, Any]) -> None:
    content = result["content"]
    assert "AI_CONTROL_LAYER_DEMO_INJECTION" in content
    assert "mail.send" in content
    assert "attacker@evil.example" in content


def _check_ci_run(result: dict[str, Any]) -> None:
    assert result["status"] == "failed"
    assert "key rotation" in result["reason"]


def _check_logs_query(result: dict[str, Any]) -> None:
    assert result["lines"] == EXPECTED_AUTH_LOG_LINES


def _check_jira_search(result: dict[str, Any]) -> None:
    tickets = result["tickets"]
    assert tickets
    assert any(ticket["key"] == "OPS-102" for ticket in tickets)


def _check_hr_employee(result: dict[str, Any]) -> None:
    assert result["found"] is True
    assert result["pesel"] == EXPECTED_PESEL


def _check_calendar_list(result: dict[str, Any]) -> None:
    assert result["events"]


def _check_mail_send(result: dict[str, Any]) -> None:
    assert result == {"sent": True, "to": "someone@example.com"}


def _check_payments_transfer(result: dict[str, Any]) -> None:
    assert result["ok"] is True
    assert result["transaction_id"].startswith("TXN-")


def _check_eu_customers_read(result: dict[str, Any]) -> None:
    assert result["found"] is True
    assert result["country"] in {"PL", "DE", "FR"}


SERVER_CASES = [
    ServerCase(
        module="github",
        expected_tools=frozenset({"list_branches", "get_readme", "delete_branch", "push_main"}),
        tool_name="get_readme",
        arguments={"repo": "vendor-sdk"},
        check=_check_github_readme,
    ),
    ServerCase(
        module="ci",
        expected_tools=frozenset({"get_run", "list_pipelines"}),
        tool_name="get_run",
        arguments={"pipeline": "e2e-login", "date": "2026-10-02"},
        check=_check_ci_run,
    ),
    ServerCase(
        module="logs_db",
        expected_tools=frozenset({"query"}),
        tool_name="query",
        arguments={"service": "auth", "since": "24h"},
        check=_check_logs_query,
    ),
    ServerCase(
        module="jira",
        expected_tools=frozenset({"search"}),
        tool_name="search",
        arguments={"query": "login"},
        check=_check_jira_search,
    ),
    ServerCase(
        module="hr_db",
        expected_tools=frozenset({"find_approver", "get_employee", "query"}),
        tool_name="get_employee",
        arguments={"employee_id": "E-1042"},
        check=_check_hr_employee,
    ),
    ServerCase(
        module="calendar",
        expected_tools=frozenset({"list"}),
        tool_name="list",
        arguments={"user": "marek.nowak"},
        check=_check_calendar_list,
    ),
    ServerCase(
        module="mail",
        expected_tools=frozenset({"send"}),
        tool_name="send",
        arguments={"to": "someone@example.com", "subject": "test", "body": "hello"},
        check=_check_mail_send,
    ),
    ServerCase(
        module="payments",
        expected_tools=frozenset({"get_balance", "transfer"}),
        tool_name="transfer",
        arguments={
            "from_account": "ACC-1001",
            "to_iban": "PL61109010140000071219812874",
            "amount": 100,
            "currency": "PLN",
        },
        check=_check_payments_transfer,
    ),
    ServerCase(
        module="eu_customers",
        expected_tools=frozenset({"read"}),
        tool_name="read",
        arguments={"customer_id": "EUC-0002"},
        check=_check_eu_customers_read,
    ),
]


@pytest.mark.integration
@pytest.mark.parametrize("case", SERVER_CASES, ids=[case.module for case in SERVER_CASES])
async def test_mcp_demo_server(case: ServerCase) -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", f"demo.mcp.{case.module}"],
        cwd=str(REPO_ROOT),
        env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
    )
    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()

        listed = await session.list_tools()
        tool_names = frozenset(tool.name for tool in listed.tools)
        assert tool_names == case.expected_tools

        result = await session.call_tool(case.tool_name, case.arguments)
        assert result.isError is False
        assert result.structuredContent is not None
        case.check(result.structuredContent)
