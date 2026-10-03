from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class Budgets(BaseModel):
    model_config = ConfigDict(frozen=True)

    per_user_tokens: int
    per_user_cost_usd: float
    max_tokens_per_request: int
    upstream_timeout_s: int
    warn_at_percent: int
    on_exceeded: Literal["block", "warn"] = "block"
    tool_calls_per_session: int | None = None
