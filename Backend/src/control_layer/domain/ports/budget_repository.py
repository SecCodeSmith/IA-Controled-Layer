from __future__ import annotations

from typing import Protocol

from control_layer.domain.models.budget_usage import BudgetUsage


class BudgetRepository(Protocol):
    async def get_usage(self, sub: str) -> BudgetUsage: ...

    async def record_usage(self, sub: str, tokens: int, cost_usd: float) -> BudgetUsage: ...

    async def reset(self, sub: str | None = None) -> None: ...
