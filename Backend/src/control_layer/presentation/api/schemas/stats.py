from __future__ import annotations

from pydantic import BaseModel

from control_layer.domain.models.protection import ProtectionInfo
from control_layer.domain.models.provider import ProviderInfo


class BudgetUserStat(BaseModel):
    sub: str
    name: str
    tokens_used: int
    tokens_limit: int
    cost_used_usd: float


class BudgetStats(BaseModel):
    users: list[BudgetUserStat] = []


class RiskStat(BaseModel):
    sub: str
    name: str
    score: int
    level: str


class LatencyStats(BaseModel):
    proxy_p50_ms: float
    proxy_p95_ms: float
    upstream_p50_ms: float
    upstream_p95_ms: float


class PolicyStatusRef(BaseModel):
    version: int
    status: str


class StatsResponse(BaseModel):
    total_calls: int
    allowed: int
    blocked: int
    masked: int
    escalated: int
    flagged: int
    by_stage: dict[str, int] = {}
    by_rule: dict[str, int] = {}
    by_owasp: dict[str, int] = {}
    by_role: dict[str, int] = {}
    budget: BudgetStats
    risk: list[RiskStat] = []
    posture_score: int
    cache_hit_ratio: float
    latency: LatencyStats
    provider: ProviderInfo
    policy: PolicyStatusRef
    protection: ProtectionInfo = ProtectionInfo()
