from __future__ import annotations

import asyncio
import re

import httpx
import pytest

from tests.conftest import ADMIN_HEADERS, call_tool, get_token

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]

_DENY_LIST = 'deny: ["**/.env", "secrets/**", "**/*.pem"]'
_READ_APP = {"repo": "web-app", "path": "src/app.py"}


async def _read_file(client: httpx.AsyncClient, token: str, path: str) -> httpx.Response:
    return await call_tool(client, token, "github", "read_file", {"repo": "web-app", "path": path})


def _bump_version(policy_text: str) -> str:
    return re.sub(r"(?m)^version: (\d+)$", lambda m: f"version: {int(m.group(1)) + 1}", policy_text)


async def _wait_for(client: httpx.AsyncClient, predicate) -> dict:
    view: dict = {}
    for _ in range(25):
        await asyncio.sleep(0.2)
        view = (await client.get("/api/policy", headers=ADMIN_HEADERS)).json()
        if predicate(view):
            break
    return view


async def test_developer_reads_allowed_repo_file(isolated_app) -> None:
    async with isolated_app(real_mcp=True) as running:
        token = await get_token(running.client, "anna.kowalska")

        response = await call_tool(running.client, token, "github", "read_file", _READ_APP)

        assert response.status_code == 200
        assert response.json()["status"] == "ALLOWED"


async def test_developer_is_blocked_from_env_file(isolated_app) -> None:
    async with isolated_app(real_mcp=True) as running:
        token = await get_token(running.client, "anna.kowalska")

        response = await _read_file(running.client, token, ".env")

        assert response.status_code == 403
        error = response.json()["error"]
        assert error["rule_id"] == "resource_scope"
        assert error["stage"] == "authorization"


@pytest.mark.parametrize("path", ["src/../.env", "/etc/passwd", "secrets/deploy.pem", "SRC/.ENV"])
async def test_developer_is_blocked_from_traversal_and_secret_paths(isolated_app, path) -> None:
    async with isolated_app(real_mcp=True) as running:
        token = await get_token(running.client, "anna.kowalska")

        response = await _read_file(running.client, token, path)

        assert response.status_code == 403
        assert response.json()["error"]["rule_id"] == "resource_scope"


async def test_hr_query_is_projected_in_text_and_structured_content(isolated_app) -> None:
    async with isolated_app(real_mcp=True) as running:
        token = await get_token(running.client, "marek.nowak")

        response = await call_tool(
            running.client, token, "hr-db", "query", {"sql_like": "SELECT * FROM employees"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "MASKED"
        assert body["rule_id"] == "resource_projection"
        assert body["stage"] == "authorization"
        result = body["result"]
        structured = str(result["structured_content"])
        for delivered in (result["content_text"], structured):
            assert "salary" not in delivered
            assert "E-2101" not in delivered
            assert "E-2001" in delivered


async def test_hr_employee_record_in_scope_still_reports_pii_masking(isolated_app) -> None:
    async with isolated_app(real_mcp=True) as running:
        token = await get_token(running.client, "marek.nowak")

        response = await call_tool(
            running.client, token, "hr-db", "get_employee", {"employee_id": "E-1042"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "MASKED"
        assert body["rule_id"] == "pii_masking"
        assert "44051401359" not in body["result"]["content_text"]


async def test_editing_resource_deny_list_takes_effect_on_hot_reload(
    isolated_app, policy_text: str
) -> None:
    async with isolated_app(policy_text=policy_text, real_mcp=True) as running:
        client = running.client
        token = await get_token(client, "anna.kowalska")
        assert (await call_tool(client, token, "github", "read_file", _READ_APP)).status_code == 200

        stricter = _bump_version(policy_text).replace(
            _DENY_LIST, 'deny: ["**/.env", "secrets/**", "**/*.pem", "src/**/*.py"]'
        )
        assert stricter != policy_text
        running.policy_path.write_text(stricter, encoding="utf-8")
        await running.app.state.container.policy_watcher.check_once()

        response = await call_tool(client, token, "github", "read_file", _READ_APP)

        assert response.status_code == 403
        assert response.json()["error"]["rule_id"] == "resource_scope"


async def test_invalid_resources_keep_last_good_policy_enforced(
    isolated_app, policy_text: str
) -> None:
    async with isolated_app(policy_text=policy_text, real_mcp=True) as running:
        client = running.client
        token = await get_token(client, "anna.kowalska")
        before = (await client.get("/api/policy", headers=ADMIN_HEADERS)).json()

        broken = _bump_version(policy_text).replace(
            "    server: github\n", "    server: github\n    unknown_key: true\n", 1
        )
        assert broken != policy_text
        running.policy_path.write_text(broken, encoding="utf-8")
        view = await _wait_for(client, lambda v: v["status"] == "ERROR")

        assert view["status"] == "ERROR"
        assert view["version"] == before["version"]
        blocked = await _read_file(client, token, ".env")
        assert blocked.status_code == 403
        assert blocked.json()["error"]["rule_id"] == "resource_scope"
        assert (await call_tool(client, token, "github", "read_file", _READ_APP)).status_code == 200
