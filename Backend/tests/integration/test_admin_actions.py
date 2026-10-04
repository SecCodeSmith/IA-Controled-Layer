from __future__ import annotations

import json

import httpx
import pytest

from tests.conftest import ADMIN_HEADERS, bearer, call_tool, get_token

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


async def _feed(api: httpx.AsyncClient) -> list[dict]:
    return (await api.get("/api/feed", headers=ADMIN_HEADERS)).json()["items"]


async def _admin_rows(api: httpx.AsyncClient) -> list[dict]:
    rows = [row for row in await _feed(api) if row["kind"] == "admin"]
    return sorted(rows, key=lambda row: row["call_id"], reverse=True)


async def _alerts(api: httpx.AsyncClient) -> list[dict]:
    return (await api.get("/api/alerts", headers=ADMIN_HEADERS)).json()["items"]


async def test_switching_protection_off_is_audited_and_alerted(api: httpx.AsyncClient) -> None:
    response = await api.put("/api/protection", json={"mode": "off"}, headers=ADMIN_HEADERS)
    assert response.status_code == 200

    rows = await _admin_rows(api)
    assert len(rows) == 1
    row = rows[0]
    assert row["target"] == "admin.protection"
    assert row["status"] == "FLAGGED"
    assert row["reason"] == "protection mode set to off (was enforce)"
    assert row["user"] == {"sub": "admin", "name": "Administrator", "role": "admin"}
    print(json.dumps(row))
    alerts = await _alerts(api)
    assert len(alerts) == 1
    assert "protection mode set to off" in alerts[0]["reason"]
    assert alerts[0]["call_id"] == row["call_id"]

    await api.put("/api/protection", json={"mode": "enforce"}, headers=ADMIN_HEADERS)
    rows = await _admin_rows(api)
    assert rows[0]["status"] == "ALLOWED"
    assert rows[0]["reason"] == "protection mode set to enforce (was off)"
    assert len(await _alerts(api)) == 1


async def test_disabling_a_rule_is_flagged(api: httpx.AsyncClient) -> None:
    await api.patch(
        "/api/policy/rules/pii_masking", json={"enabled": False}, headers=ADMIN_HEADERS
    )

    rows = await _admin_rows(api)
    assert [(r["target"], r["status"], r["reason"]) for r in rows] == [
        ("admin.rule_override", "FLAGGED", "rule pii_masking disabled")
    ]

    await api.patch("/api/policy/rules/pii_masking", json={"enabled": True}, headers=ADMIN_HEADERS)
    assert (await _admin_rows(api))[0]["status"] == "ALLOWED"


async def test_unknown_rule_patch_records_nothing(api: httpx.AsyncClient) -> None:
    await api.patch("/api/policy/rules/ghost", json={"enabled": False}, headers=ADMIN_HEADERS)

    assert await _admin_rows(api) == []


async def test_policy_reload_is_recorded_as_allowed(api: httpx.AsyncClient) -> None:
    assert (await api.post("/api/policy/reload", headers=ADMIN_HEADERS)).status_code == 200

    rows = await _admin_rows(api)
    assert [(r["target"], r["status"]) for r in rows] == [("admin.policy_reload", "ALLOWED")]


async def test_clearing_logs_leaves_exactly_the_admin_row(api: httpx.AsyncClient) -> None:
    token = await get_token(api, "anna.kowalska")
    await call_tool(api, token, "ci", "get_run", {"pipeline": "p", "date": "d"})

    await api.post("/api/logs/clear", headers=ADMIN_HEADERS)

    rows = await _feed(api)
    assert [(r["kind"], r["target"], r["status"], r["reason"]) for r in rows] == [
        ("admin", "admin.logs", "FLAGGED", "logs cleared")
    ]


async def test_demo_reset_is_recorded_after_clearing(api: httpx.AsyncClient) -> None:
    await api.post("/api/demo/reset", headers=ADMIN_HEADERS)

    rows = await _feed(api)
    assert [(r["target"], r["reason"]) for r in rows] == [
        ("admin.reset", "demo reset (scope=all)")
    ]


async def test_protection_state_exposes_who_and_when(api: httpx.AsyncClient) -> None:
    initial = (await api.get("/api/protection", headers=ADMIN_HEADERS)).json()
    assert initial["changed_at"] is None
    assert initial["changed_by"] is None

    await api.put("/api/protection", json={"mode": "monitor"}, headers=ADMIN_HEADERS)

    state = (await api.get("/api/protection", headers=ADMIN_HEADERS)).json()
    assert state["changed_by"] == "admin"
    assert state["changed_at"]
    health = (await api.get("/health")).json()["protection"]
    assert (health["mode"], health["changed_by"], health["changed_at"]) == (
        "monitor",
        "admin",
        state["changed_at"],
    )
    stats = (await api.get("/api/stats", headers=ADMIN_HEADERS)).json()["protection"]
    assert stats["changed_by"] == "admin"
    token = await get_token(api, "anna.kowalska")
    me = (await api.get("/v1/me", headers=bearer(token))).json()["protection"]
    assert me == {"mode": "monitor", "changed_at": state["changed_at"]}


async def test_admin_rows_do_not_count_as_traffic_in_stats(api: httpx.AsyncClient) -> None:
    await api.put("/api/protection", json={"mode": "off"}, headers=ADMIN_HEADERS)
    await api.put("/api/protection", json={"mode": "enforce"}, headers=ADMIN_HEADERS)

    stats = (await api.get("/api/stats", headers=ADMIN_HEADERS)).json()

    assert stats["total_calls"] == 0
    assert stats["flagged"] == 0
    assert stats["posture_score"] == 100
    assert stats["admin_actions"] == 2
    assert "admin" not in stats["by_role"]
