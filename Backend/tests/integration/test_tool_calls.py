from __future__ import annotations

import httpx
import pytest

from tests.conftest import bearer, call_tool, get_token

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


async def test_allowed_tool_call(api: httpx.AsyncClient) -> None:
    token = await get_token(api, "anna.kowalska")
    response = await call_tool(
        api, token, "ci", "get_run", {"pipeline": "e2e-login", "date": "2026-10-02"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ALLOWED"
    assert body["items_masked"] == 0
    assert body["result"]["is_error"] is False
    assert body["result"]["content_text"]


async def test_pii_in_tool_result_is_masked(api: httpx.AsyncClient) -> None:
    token = await get_token(api, "anna.kowalska")
    response = await call_tool(
        api, token, "logs-db", "query", {"service": "auth", "since": "24h"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "MASKED"
    assert body["stage"] == "dlp"
    assert body["rule_id"] == "pii_masking"
    assert body["items_masked"] == 3
    text = body["result"]["content_text"]
    assert "[EMAIL_1]" in text
    assert "@example.com" not in text


async def test_pesel_in_hr_report_is_masked(api: httpx.AsyncClient) -> None:
    token = await get_token(api, "marek.nowak")
    response = await call_tool(api, token, "hr-db", "get_employee", {"employee_id": "E-1042"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "MASKED"
    assert body["rule_id"] == "pii_masking"
    assert "44051401359" not in body["result"]["content_text"]


async def test_role_provisioning_blocks_developer_on_hr_db(api: httpx.AsyncClient) -> None:
    token = await get_token(api, "anna.kowalska")
    response = await call_tool(api, token, "hr-db", "find_approver", {"request": "test-accounts"})
    assert response.status_code == 403
    error = response.json()["error"]
    assert error["code"] == "policy_violation"
    assert error["stage"] == "authorization"
    assert error["rule_id"] == "role_provisioning"
    assert error["owasp"] == ["ASI03", "LLM06"]
    assert error["call_id"]


async def test_data_residency_blocks_us_user(api: httpx.AsyncClient) -> None:
    token = await get_token(api, "john.smith")
    response = await call_tool(api, token, "eu-customers", "read", {"customer_id": "EUC-0001"})
    assert response.status_code == 403
    assert response.json()["error"]["rule_id"] == "data_residency"


async def test_direct_push_to_main_is_blocked(api: httpx.AsyncClient) -> None:
    token = await get_token(api, "anna.kowalska")
    response = await call_tool(
        api, token, "github", "push_main", {"repo": "web-app", "message": "x"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["rule_id"] == "direct_push_to_main"


async def _escalate(api: httpx.AsyncClient, token: str, branch: str = "feature/old-login") -> dict:
    response = await call_tool(
        api, token, "github", "delete_branch", {"repo": "web-app", "branch": branch}
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "ESCALATED"
    assert body["stage"] == "authorization"
    assert body["rule_id"] == "destructive_requires_approval"
    assert body["approval"]["id"].startswith("ap_")
    return body


async def test_escalation_then_approve_executes_once(api: httpx.AsyncClient) -> None:
    token = await get_token(api, "anna.kowalska")
    escalated = await _escalate(api, token)
    approval_id = escalated["approval"]["id"]

    detail = await api.get(f"/v1/approvals/{approval_id}", headers=bearer(token))
    assert detail.status_code == 200
    assert detail.json()["status"] == "pending"
    assert detail.json()["tool"] == "github.delete_branch"

    approved = await api.post(f"/v1/approvals/{approval_id}/approve", headers=bearer(token))
    assert approved.status_code == 200
    body = approved.json()
    assert body["result"]["structured_content"]["deleted"] is True

    again = await api.post(f"/v1/approvals/{approval_id}/approve", headers=bearer(token))
    assert again.status_code in (404, 409)


async def test_escalation_then_reject_never_executes(api: httpx.AsyncClient) -> None:
    token = await get_token(api, "anna.kowalska")
    approval_id = (await _escalate(api, token))["approval"]["id"]

    rejected = await api.post(f"/v1/approvals/{approval_id}/reject", headers=bearer(token))
    assert rejected.status_code == 200
    assert rejected.json() == {"id": approval_id, "status": "rejected"}

    after = await api.post(f"/v1/approvals/{approval_id}/approve", headers=bearer(token))
    assert after.status_code in (404, 409)


async def test_other_users_cannot_act_on_an_approval(api: httpx.AsyncClient) -> None:
    anna = await get_token(api, "anna.kowalska")
    john = await get_token(api, "john.smith")
    approval_id = (await _escalate(api, anna))["approval"]["id"]
    response = await api.post(f"/v1/approvals/{approval_id}/approve", headers=bearer(john))
    assert response.status_code == 404


async def test_unknown_approval_is_404(api: httpx.AsyncClient) -> None:
    token = await get_token(api, "anna.kowalska")
    response = await api.get("/v1/approvals/ap_missing", headers=bearer(token))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_exfiltration_sequence_is_blocked(isolated_app, policy_text: str) -> None:
    async with isolated_app(policy_text=policy_text, real_mcp=True) as running:
        client = running.client
        token = await get_token(client, "anna.kowalska")
        read = await call_tool(
            client, token, "github", "get_readme", {"repo": "web-app"}, session="s-exfil"
        )
        assert read.status_code == 200
        send = await call_tool(
            client,
            token,
            "mail",
            "send",
            {"to": "outside@external-domain.com", "subject": "notes", "body": "readme"},
            session="s-exfil",
        )
        assert send.status_code == 403
        error = send.json()["error"]
        assert error["stage"] == "dlp"
        assert error["rule_id"] == "external_send_after_untrusted_read"

        other = await call_tool(
            client,
            token,
            "mail",
            "send",
            {"to": "outside@external-domain.com", "subject": "notes", "body": "hello"},
            session="s-clean",
        )
        assert other.status_code == 200
