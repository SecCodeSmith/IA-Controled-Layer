from __future__ import annotations

from pathlib import Path

import yaml

from control_layer.domain.models.user import DemoUser


class YamlUserRepository:
    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._users: dict[str, DemoUser] = {}
        self._load()

    def _load(self) -> None:
        data = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        self._users = {
            entry["sub"]: DemoUser(
                sub=entry["sub"],
                name=entry["name"],
                initials=entry["initials"],
                role=entry["role"],
                location=entry["location"],
                region=entry["region"],
                agent_id=entry["agent_id"],
                mcp_servers=list(entry.get("mcp_servers", [])),
            )
            for entry in data.get("users", [])
        }

    async def list_all(self) -> list[DemoUser]:
        return list(self._users.values())

    async def get(self, sub: str) -> DemoUser | None:
        return self._users.get(sub)
