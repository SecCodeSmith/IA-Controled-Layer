from __future__ import annotations

from pathlib import Path

import pytest

from control_layer.infrastructure.users.yaml_user_repository import YamlUserRepository

REAL_USERS_FILE = Path(__file__).resolve().parents[4] / "config" / "users.yaml"

SAMPLE_YAML = """
users:
  - sub: anna.kowalska
    name: Anna Kowalska
    initials: AK
    role: developer
    location: "Krakow, PL"
    region: PL
    agent_id: agent-anna-dev-7f3a
    mcp_servers: [github, ci, logs-db, jira]
  - sub: marek.nowak
    name: Marek Nowak
    initials: MN
    role: hr
    location: "Warsaw, PL"
    region: PL
    agent_id: agent-marek-hr-3c91
    mcp_servers: [hr-db, calendar, mail]
"""


async def test_list_all_parses_sample_file(tmp_path: Path) -> None:
    path = tmp_path / "users.yaml"
    path.write_text(SAMPLE_YAML, encoding="utf-8")
    repo = YamlUserRepository(path)

    users = await repo.list_all()

    assert {u.sub for u in users} == {"anna.kowalska", "marek.nowak"}
    anna = next(u for u in users if u.sub == "anna.kowalska")
    assert anna.name == "Anna Kowalska"
    assert anna.initials == "AK"
    assert anna.role == "developer"
    assert anna.location == "Krakow, PL"
    assert anna.region == "PL"
    assert anna.agent_id == "agent-anna-dev-7f3a"
    assert anna.mcp_servers == ["github", "ci", "logs-db", "jira"]


async def test_get_existing_user(tmp_path: Path) -> None:
    path = tmp_path / "users.yaml"
    path.write_text(SAMPLE_YAML, encoding="utf-8")
    repo = YamlUserRepository(path)

    user = await repo.get("marek.nowak")

    assert user is not None
    assert user.name == "Marek Nowak"


async def test_get_missing_user_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "users.yaml"
    path.write_text(SAMPLE_YAML, encoding="utf-8")
    repo = YamlUserRepository(path)

    assert await repo.get("missing") is None


@pytest.mark.skipif(not REAL_USERS_FILE.exists(), reason="Backend/config/users.yaml not present")
async def test_loads_real_sample_users_file() -> None:
    repo = YamlUserRepository(REAL_USERS_FILE)

    users = await repo.list_all()

    subs = {u.sub for u in users}
    assert {"anna.kowalska", "marek.nowak", "john.smith", "ewa.zielinska"}.issubset(subs)
