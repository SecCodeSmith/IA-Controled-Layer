from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from control_layer.application.telemetry.metrics_collector import MetricsView
from control_layer.application.use_cases.admin._shared import load_all_call_records
from control_layer.domain.models.audit import CallRecord
from control_layer.domain.models.provider import ProviderInfo
from control_layer.domain.ports.audit_repository import AuditRepository
from control_layer.domain.ports.budget_repository import BudgetRepository
from control_layer.domain.ports.model_provider import ModelProvider
from control_layer.domain.ports.policy_repository import PolicyRepository
from control_layer.domain.ports.risk_repository import RiskRepository


class _HasSubAndName(Protocol):
    sub: str
    name: str


class _UserDirectory(Protocol):
    async def list_all(self) -> list[_HasSubAndName]: ...


class _MetricsSource(Protocol):
    def snapshot(self) -> MetricsView: ...


class BudgetUserStat(BaseModel):
    model_config = ConfigDict(frozen=True)

    sub: str
    name: str
    tokens_used: int
    tokens_limit: int
    cost_used_usd: float


class BudgetStats(BaseModel):
    model_config = ConfigDict(frozen=True)

    users: list[BudgetUserStat] = Field(default_factory=list)


class RiskStat(BaseModel):
    model_config = ConfigDict(frozen=True)

    sub: str
    name: str
    score: int
    level: str


class LatencyStats(BaseModel):
    model_config = ConfigDict(frozen=True)

    proxy_p50_ms: float
    proxy_p95_ms: float
    upstream_p50_ms: float
    upstream_p95_ms: float


class PolicyStatusRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: int
    status: str


class StatsView(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_calls: int
    allowed: int
    blocked: int
    masked: int
    escalated: int
    flagged: int
    by_stage: dict[str, int] = Field(default_factory=dict)
    by_rule: dict[str, int] = Field(default_factory=dict)
    by_owasp: dict[str, int] = Field(default_factory=dict)
    by_role: dict[str, int] = Field(default_factory=dict)
    budget: BudgetStats
    risk: list[RiskStat] = Field(default_factory=list)
    posture_score: int
    cache_hit_ratio: float
    latency: LatencyStats
    provider: ProviderInfo
    policy: PolicyStatusRef


def _bump(counter: dict[str, int], key: str | None) -> None:
    if key is None:
        return
    counter[key] = counter.get(key, 0) + 1


def _tally(records: list[CallRecord]) -> tuple[int, int, int, int, int, dict, dict, dict, dict]:
    allowed = blocked = masked = escalated = flagged = 0
    by_stage: dict[str, int] = {}
    by_rule: dict[str, int] = {}
    by_owasp: dict[str, int] = {}
    by_role: dict[str, int] = {}

    for record in records:
        status = record.decision.status.value
        if status == "ALLOWED":
            allowed += 1
        elif status == "BLOCKED":
            blocked += 1
        elif status == "MASKED":
            masked += 1
        elif status == "ESCALATED":
            escalated += 1
        elif status == "FLAGGED":
            flagged += 1

        if record.decision.stage is not None:
            _bump(by_stage, record.decision.stage.value)
        _bump(by_rule, record.decision.rule_id)
        for owasp_id in record.decision.owasp:
            _bump(by_owasp, owasp_id)
        _bump(by_role, record.identity.role.value)

    return allowed, blocked, masked, escalated, flagged, by_stage, by_rule, by_owasp, by_role


def _posture_score(total: int, allowed: int, masked: int) -> int:
    if total == 0:
        return 100
    return round(100 * (allowed + masked) / total)


class StatsCalculator:
    def __init__(
        self,
        audit_repository: AuditRepository,
        budget_repository: BudgetRepository,
        risk_repository: RiskRepository,
        metrics_collector: _MetricsSource,
        policy_repository: PolicyRepository,
        model_provider: ModelProvider,
        user_repository: _UserDirectory,
    ) -> None:
        self._audit_repository = audit_repository
        self._budget_repository = budget_repository
        self._risk_repository = risk_repository
        self._metrics_collector = metrics_collector
        self._policy_repository = policy_repository
        self._model_provider = model_provider
        self._user_repository = user_repository

    async def compute(self) -> StatsView:
        records = await load_all_call_records(self._audit_repository)
        (
            allowed,
            blocked,
            masked,
            escalated,
            flagged,
            by_stage,
            by_rule,
            by_owasp,
            by_role,
        ) = _tally(records)
        total = len(records)

        users = await self._user_repository.list_all()
        names_by_sub = {user.sub: user.name for user in users}

        budget_user_stats: list[BudgetUserStat] = []
        for user in users:
            usage = await self._budget_repository.get_usage(user.sub)
            budget_user_stats.append(
                BudgetUserStat(
                    sub=user.sub,
                    name=user.name,
                    tokens_used=usage.tokens_used,
                    tokens_limit=usage.tokens_limit,
                    cost_used_usd=usage.cost_used_usd,
                )
            )
        budget_stats = BudgetStats(users=budget_user_stats)

        risk_profiles = await self._risk_repository.list_all()
        risk_stats = [
            RiskStat(
                sub=profile.sub,
                name=names_by_sub.get(profile.sub, profile.sub),
                score=profile.score,
                level=profile.level.value,
            )
            for profile in risk_profiles
        ]

        metrics = self._metrics_collector.snapshot()
        provider_info = self._model_provider.describe()
        policy_status = await self._policy_repository.status()

        return StatsView(
            total_calls=total,
            allowed=allowed,
            blocked=blocked,
            masked=masked,
            escalated=escalated,
            flagged=flagged,
            by_stage=by_stage,
            by_rule=by_rule,
            by_owasp=by_owasp,
            by_role=by_role,
            budget=budget_stats,
            risk=risk_stats,
            posture_score=_posture_score(total, allowed, masked),
            cache_hit_ratio=metrics.cache.hit_ratio,
            latency=LatencyStats(
                proxy_p50_ms=metrics.proxy.p50_ms,
                proxy_p95_ms=metrics.proxy.p95_ms,
                upstream_p50_ms=metrics.upstream.p50_ms,
                upstream_p95_ms=metrics.upstream.p95_ms,
            ),
            provider=provider_info,
            policy=PolicyStatusRef(
                version=policy_status.get("version", 0),
                status=policy_status.get("status", "LOADED"),
            ),
        )
