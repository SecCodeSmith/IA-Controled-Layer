from __future__ import annotations

from typing import Protocol

from control_layer.domain.models.user import DemoUser


class UserRepository(Protocol):
    async def list_all(self) -> list[DemoUser]: ...

    async def get(self, sub: str) -> DemoUser | None: ...
