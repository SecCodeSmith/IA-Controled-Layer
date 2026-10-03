from __future__ import annotations

from control_layer.domain.models.user import DemoUser
from control_layer.domain.ports.user_repository import UserRepository


class ListUsersUseCase:
    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository

    async def execute(self) -> list[DemoUser]:
        return await self._user_repository.list_all()
