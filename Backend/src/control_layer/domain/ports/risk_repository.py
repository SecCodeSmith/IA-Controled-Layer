from __future__ import annotations

from typing import Protocol

from control_layer.domain.models.risk import RiskProfile


class RiskRepository(Protocol):
    async def get(self, sub: str) -> RiskProfile: ...

    async def update(self, profile: RiskProfile) -> None: ...

    async def list_all(self) -> list[RiskProfile]: ...
