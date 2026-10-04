from __future__ import annotations

import httpx
import pytest

from tests.conftest import ADMIN_HEADERS, call_tool, get_token

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]

REAL_EMAIL = "k.wrona@example.com"


async def _audit(api: httpx.AsyncClient, call_id: str) -> dict:
    response = await api.get(f"/api/audit/{call_id}", headers=ADMIN_HEADERS)
    assert response.status_code == 200, response.text
    return response.json()


async def test_masked_email_is_restored_for_mail_send_in_the_same_session(
    api: httpx.AsyncClient,
) -> None:
    token = await get_token(api, "marek.nowak")
    session = "vault-email-session"

    found = await call_tool(
        api, token, "hr-db", "find_approver", {"request": "test-accounts"}, session=session
    )
    assert found.status_code == 200, found.text
    assert found.json()["status"] == "MASKED"
    assert "[EMAIL_1]" in found.json()["result"]["content_text"]
    assert REAL_EMAIL not in found.json()["result"]["content_text"]

    sent = await call_tool(
        api,
        token,
        "mail",
        "send",
        {"to": "[EMAIL_1]", "subject": "Reminder", "body": "Please approve"},
        session=session,
    )
    assert sent.status_code == 200, sent.text
    body = sent.json()
    assert body["items_restored"] == 1
    assert "[EMAIL_1]" in body["result"]["content_text"]
    assert REAL_EMAIL not in body["result"]["content_text"]

    detail = await _audit(api, body["call_id"])
    assert REAL_EMAIL in detail["response"]["raw"]
    assert "[EMAIL_1]" in detail["response"]["delivered"]
    assert detail["items_restored"] == 1
    assert detail["request"]["payload"]["to"] == "[EMAIL_1]"


async def test_pesel_placeholder_is_never_restored(api: httpx.AsyncClient) -> None:
    token = await get_token(api, "marek.nowak")
    session = "vault-pesel-session"

    employee = await call_tool(
        api, token, "hr-db", "get_employee", {"employee_id": "E-1042"}, session=session
    )
    assert employee.status_code == 200, employee.text
    assert "[PESEL_1]" in employee.json()["result"]["content_text"]

    sent = await call_tool(
        api,
        token,
        "mail",
        "send",
        {"to": "[PESEL_1]", "subject": "S", "body": "PESEL: [PESEL_1]"},
        session=session,
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["items_restored"] == 0

    detail = await _audit(api, sent.json()["call_id"])
    assert "[PESEL_1]" in detail["response"]["raw"]
    assert detail["request"]["payload"]["body"] == "PESEL: [PESEL_1]"
    assert "44051401359" not in detail["response"]["raw"]


async def test_placeholder_from_another_session_is_not_restored(api: httpx.AsyncClient) -> None:
    token = await get_token(api, "marek.nowak")
    await call_tool(
        api, token, "hr-db", "find_approver", {"request": "test-accounts"}, session="vault-a"
    )

    sent = await call_tool(
        api,
        token,
        "mail",
        "send",
        {"to": "[EMAIL_1]", "subject": "S", "body": "b"},
        session="vault-b",
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["items_restored"] == 0


async def test_same_session_id_from_another_user_is_not_restored(
    api: httpx.AsyncClient,
) -> None:
    marek = await get_token(api, "marek.nowak")
    anna = await get_token(api, "anna.kowalska")
    session = "vault-shared-session"
    found = await call_tool(
        api, marek, "hr-db", "find_approver", {"request": "test-accounts"}, session=session
    )
    assert "[EMAIL_1]" in found.json()["result"]["content_text"]

    sent = await call_tool(
        api,
        anna,
        "mail",
        "send",
        {"to": "[EMAIL_1]", "subject": "S", "body": "b"},
        session=session,
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["items_restored"] == 0
    assert REAL_EMAIL not in sent.json()["result"]["content_text"]
