from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BudgetUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    tokens_used: int
    tokens_limit: int
    cost_used_usd: float
    cost_limit_usd: float
    resets_at: datetime
