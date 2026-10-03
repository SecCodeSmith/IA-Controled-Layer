from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from control_layer.domain.models.identity import Identity
from control_layer.domain.models.protection import ProtectionInfo
from control_layer.domain.models.provider import ProviderInfo
from control_layer.domain.models.tool import ToolDescriptor


class PolicyRef(BaseModel):
    name: str
    version: int


class BudgetSummary(BaseModel):
    tokens_used: int
    tokens_limit: int
    cost_used_usd: float
    cost_limit_usd: float
    resets_at: datetime


class RiskSummary(BaseModel):
    score: int
    level: str


class MeResponse(BaseModel):
    identity: Identity
    tools: list[ToolDescriptor]
    policy: PolicyRef
    budget: BudgetSummary
    risk: RiskSummary
    provider: ProviderInfo
    protection: ProtectionInfo = ProtectionInfo()
