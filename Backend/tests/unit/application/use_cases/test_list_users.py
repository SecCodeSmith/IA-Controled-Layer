from __future__ import annotations

from control_layer.application.use_cases.list_users import ListUsersUseCase
from control_layer.domain.models.enums import Role
from control_layer.domain.models.user import DemoUser


class _FakeUserRepository:
    def __init__(self, users: list[DemoUser]) -> None:
        self._users = users

    async def list_all(self) -> list[DemoUser]:
        return self._users

    async def get(self, sub: str) -> DemoUser | None:
        return next((u for u in self._users if u.sub == sub), None)


async def test_returns_all_users() -> None:
    users = [
        DemoUser(
            sub="anna.kowalska",
            name="Anna Kowalska",
            initials="AK",
            role=Role.developer,
            location="Krakow, PL",
            region="PL",
            agent_id="agent-anna",
            mcp_servers=["github"],
        )
    ]
    use_case = ListUsersUseCase(_FakeUserRepository(users))
    assert await use_case.execute() == users
