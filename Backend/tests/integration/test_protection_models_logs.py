from __future__ import annotations

import httpx
import pytest

from tests.conftest import ADMIN_HEADERS, RunningApp, bearer, call_tool, get_token, read_sse

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


def _ollama_models() -> list[str]:
    try:
        response = httpx.get("http://localhost:11434/api/tags", timeout=1.5)
        return [m["name"] for m in response.json().get("models", [])]
    except Exception:
        return []


async def _put_mode(api: httpx.AsyncClient, mode: str) -> httpx.Response:
    return await api.put("/api/protection", json={"mode": mode}, headers=ADMIN_HEADERS)


async def _hr_query(api: httpx.AsyncClient) -> httpx.Response:
    token = await get_token(api, "anna.kowalska")
    return await call_tool(api, token, "hr-db", "query", {"query": "all"})


async def test_protection_defaults_and_round_trip(api: httpx.AsyncClient) -> None:
    initial = await api.get("/api/protection", headers=ADMIN_HEADERS)
    assert initial.json() == {"mode": "enforce", "rule_overrides": {}, "disabled_rules": []}

    updated = await _put_mode(api, "monitor")
    assert updated.status_code == 200
    assert updated.json()["mode"] == "monitor"
    assert (await api.get("/api/protection", headers=ADMIN_HEADERS)).json()["mode"] == "monitor"

    invalid = await _put_mode(api, "paranoid")
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"


async def test_protection_routes_require_the_admin_token(api: httpx.AsyncClient) -> None:
    assert (await api.get("/api/protection")).status_code == 401
    assert (await api.put("/api/protection", json={"mode": "off"})).status_code == 401
    assert (await api.delete("/api/protection/overrides")).status_code == 401
    patch = await api.patch("/api/policy/rules/pii_masking", json={"enabled": False})
    assert patch.status_code == 401
    assert (await api.get("/api/models")).status_code == 401
    assert (await api.post("/api/logs/clear")).status_code == 401


async def test_enforce_blocks_monitor_flags_and_off_allows_a_blocked_tool(
    api: httpx.AsyncClient,
) -> None:
    blocked = await _hr_query(api)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["rule_id"] == "role_provisioning"

    await _put_mode(api, "monitor")
    flagged = await _hr_query(api)
    assert flagged.status_code == 200
    body = flagged.json()
    assert body["status"] == "FLAGGED"
    assert body["rule_id"] == "role_provisioning"
    assert body["stage"] == "authorization"

    await _put_mode(api, "off")
    allowed = await _hr_query(api)
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "ALLOWED"

    feed = await api.get("/api/feed", headers=ADMIN_HEADERS)
    statuses = [i["status"] for i in feed.json()["items"] if i["target"] == "hr-db.query"]
    assert sorted(statuses) == ["ALLOWED", "BLOCKED", "FLAGGED"]


async def test_off_mode_still_rejects_an_invalid_token(api: httpx.AsyncClient) -> None:
    await _put_mode(api, "off")

    response = await call_tool(api, "not-a-token", "ci", "get_run", {"pipeline": "p", "date": "d"})

    assert response.status_code == 401


async def test_rule_override_disables_and_restores_pii_masking(api: httpx.AsyncClient) -> None:
    token = await get_token(api, "anna.kowalska")
    args = {"service": "auth", "since": "24h"}
    assert (await call_tool(api, token, "logs-db", "query", args)).json()["status"] == "MASKED"

    patched = await api.patch(
        "/api/policy/rules/pii_masking", json={"enabled": False}, headers=ADMIN_HEADERS
    )
    assert patched.json() == {"rule_id": "pii_masking", "enabled": False, "overridden": True}

    protection = (await api.get("/api/protection", headers=ADMIN_HEADERS)).json()
    assert protection["rule_overrides"] == {"pii_masking": False}
    assert protection["disabled_rules"] == ["pii_masking"]

    policy = (await api.get("/api/policy", headers=ADMIN_HEADERS)).json()
    rule = next(r for r in policy["rules_by_stage"]["dlp"] if r["id"] == "pii_masking")
    assert (rule["enabled"], rule["overridden"]) == (False, True)
    others = [r for r in policy["rules_by_stage"]["authorization"] if r["id"] != "pii_masking"]
    assert others
    assert all(r["overridden"] is False and r["enabled"] is True for r in others)

    raw = await call_tool(api, token, "logs-db", "query", args)
    assert raw.json()["status"] == "ALLOWED"
    assert "@example.com" in raw.json()["result"]["content_text"]

    await api.patch("/api/policy/rules/pii_masking", json={"enabled": True}, headers=ADMIN_HEADERS)
    again = await call_tool(api, token, "logs-db", "query", args)
    assert again.json()["status"] == "MASKED"

    cleared = await api.delete("/api/protection/overrides", headers=ADMIN_HEADERS)
    assert cleared.json() == {"mode": "enforce", "rule_overrides": {}, "disabled_rules": []}


async def test_patching_an_unknown_rule_returns_404_envelope(api: httpx.AsyncClient) -> None:
    response = await api.patch(
        "/api/policy/rules/ghost", json={"enabled": False}, headers=ADMIN_HEADERS
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_protection_mode_is_exposed_on_stats_health_and_me(api: httpx.AsyncClient) -> None:
    await _put_mode(api, "monitor")
    token = await get_token(api, "anna.kowalska")

    stats = await api.get("/api/stats", headers=ADMIN_HEADERS)
    health = await api.get("/health")
    me = await api.get("/v1/me", headers=bearer(token))

    assert stats.json()["protection"] == {"mode": "monitor"}
    assert health.json()["protection"] == {"mode": "monitor"}
    assert me.json()["protection"] == {"mode": "monitor"}


async def test_stats_sse_event_carries_protection(
    api: httpx.AsyncClient, shared_app: RunningApp
) -> None:
    await _put_mode(api, "monitor")
    token = await get_token(api, "anna.kowalska")

    async def trigger() -> None:
        await call_tool(api, token, "ci", "get_run", {"pipeline": "e2e-login", "date": "d"})

    events = await read_sse(
        shared_app.app,
        "/api/feed/stream?admin_token=admin-dev-token",
        until=lambda seen: any(name == "stats" for name, _ in seen),
        trigger=trigger,
    )

    stats = next(data for name, data in events if name == "stats")
    assert stats["protection"] == {"mode": "monitor"}


async def test_demo_reset_restores_enforce_and_clears_overrides(api: httpx.AsyncClient) -> None:
    await _put_mode(api, "off")
    await api.patch("/api/policy/rules/pii_masking", json={"enabled": False}, headers=ADMIN_HEADERS)

    await api.post("/api/demo/reset", headers=ADMIN_HEADERS)

    state = (await api.get("/api/protection", headers=ADMIN_HEADERS)).json()
    assert state == {"mode": "enforce", "rule_overrides": {}, "disabled_rules": []}


async def test_models_list_contains_mock_and_marks_allowlisted_models(
    api: httpx.AsyncClient,
) -> None:
    response = await api.get("/api/models", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["active"] == {"name": "mock", "model": "mock"}
    available = {(m["provider"], m["model"]): m for m in body["available"]}
    assert available[("mock", "mock")] == {
        "provider": "mock",
        "model": "mock",
        "allowed": True,
        "size_gb": None,
    }
    for name in _ollama_models():
        entry = available[("ollama", name)]
        assert entry["allowed"] is (name in {"qwen2.5:7b", "qwen2.5:3b"})
        assert entry["size_gb"] is None or entry["size_gb"] > 0


async def test_select_unknown_model_returns_404(api: httpx.AsyncClient) -> None:
    response = await api.put(
        "/api/models", json={"provider": "ollama", "model": "no-such:1b"}, headers=ADMIN_HEADERS
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_select_mock_is_reflected_by_me_and_health(api: httpx.AsyncClient) -> None:
    token = await get_token(api, "anna.kowalska")

    selected = await api.put(
        "/api/models", json={"provider": "mock", "model": "mock"}, headers=ADMIN_HEADERS
    )

    assert selected.status_code == 200
    assert selected.json() == {"name": "mock", "model": "mock"}
    me = await api.get("/v1/me", headers=bearer(token))
    assert me.json()["provider"] == {"name": "mock", "model": "mock"}
    assert (await api.get("/health")).json()["provider"] == {"name": "mock", "model": "mock"}


@pytest.mark.skipif("qwen2.5:7b" not in _ollama_models(), reason="Ollama model not available")
async def test_switch_to_ollama_and_back_changes_the_active_provider(
    api: httpx.AsyncClient,
) -> None:
    token = await get_token(api, "anna.kowalska")
    try:
        selected = await api.put(
            "/api/models",
            json={"provider": "ollama", "model": "qwen2.5:7b"},
            headers=ADMIN_HEADERS,
        )
        assert selected.json() == {"name": "ollama", "model": "qwen2.5:7b"}
        me = await api.get("/v1/me", headers=bearer(token))
        assert me.json()["provider"] == {"name": "ollama", "model": "qwen2.5:7b"}
        stats = await api.get("/api/stats", headers=ADMIN_HEADERS)
        assert stats.json()["provider"]["name"] == "ollama"
    finally:
        await api.put(
            "/api/models", json={"provider": "mock", "model": "mock"}, headers=ADMIN_HEADERS
        )
    me = await api.get("/v1/me", headers=bearer(token))
    assert me.json()["provider"]["name"] == "mock"


async def test_clear_logs_empties_audit_alerts_and_excel(
    api: httpx.AsyncClient, shared_app: RunningApp
) -> None:
    token = await get_token(api, "anna.kowalska")
    await call_tool(api, token, "logs-db", "query", {"service": "auth", "since": "24h"})
    await _hr_query(api)
    assert (await api.get("/api/audit", headers=ADMIN_HEADERS)).json()["items"]
    assert (await api.get("/api/alerts", headers=ADMIN_HEADERS)).json()["items"]
    assert shared_app.settings.alerts_xlsx_path.exists()
    await _put_mode(api, "monitor")

    response = await api.post("/api/logs/clear", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "cleared": ["audit", "alerts", "alerts_xlsx", "audit_jsonl", "metrics", "feed"],
    }
    assert (await api.get("/api/audit", headers=ADMIN_HEADERS)).json()["items"] == []
    assert (await api.get("/api/alerts", headers=ADMIN_HEADERS)).json()["items"] == []
    assert (await api.get("/api/feed", headers=ADMIN_HEADERS)).json()["items"] == []
    assert not shared_app.settings.alerts_xlsx_path.exists()
    assert shared_app.settings.audit_jsonl_path.read_text(encoding="utf-8") == ""
    assert (await api.get("/api/stats", headers=ADMIN_HEADERS)).json()["total_calls"] == 0
    assert (await api.get("/api/protection", headers=ADMIN_HEADERS)).json()["mode"] == "monitor"

    await _put_mode(api, "enforce")
    next_call = await call_tool(api, token, "ci", "get_run", {"pipeline": "p", "date": "d"})
    assert next_call.json()["call_id"] == "c_000001"
