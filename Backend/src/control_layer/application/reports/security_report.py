from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from control_layer.application.reports.markdown import render_markdown
from control_layer.application.reports.owasp_catalog import OWASP_CATALOG
from control_layer.application.use_cases.admin._shared import (
    filter_by_period,
    load_all_call_records,
)
from control_layer.application.use_cases.admin.stats import posture_score, tally_call_records
from control_layer.domain.models.alert import Alert
from control_layer.domain.ports.alert_store import AlertStore
from control_layer.domain.ports.audit_repository import AuditRepository

_TOP_N = 10
_ALERT_OVERFETCH_LIMIT = 5000
_BLOCK_RECOMMENDATION_THRESHOLD = 3
_RULE_RECOMMENDATION_THRESHOLD = 10
_BUDGET_RECOMMENDATION_PERCENT = 80


class OwaspCoverageRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    events: int
    status: str


class ReportView(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_at: datetime
    period: str
    summary: dict
    top_rules: list[dict] = Field(default_factory=list)
    top_users: list[dict] = Field(default_factory=list)
    owasp_coverage: list[OwaspCoverageRow] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    markdown: str


class _ComputesStats(Protocol):
    async def compute(self) -> object: ...


def _tally_top_rules(alerts: list[Alert]) -> list[dict]:
    counts: dict[str, dict] = {}
    for alert in alerts:
        if alert.rule_id is None:
            continue
        entry = counts.setdefault(
            alert.rule_id, {"rule_id": alert.rule_id, "count": 0, "stage": alert.stage.value}
        )
        entry["count"] += 1
    return sorted(counts.values(), key=lambda e: e["count"], reverse=True)[:_TOP_N]


def _tally_top_users(alerts: list[Alert]) -> list[dict]:
    counts: dict[str, dict] = {}
    for alert in alerts:
        sub = alert.user.sub
        entry = counts.setdefault(
            sub,
            {"sub": sub, "name": alert.user.name, "blocked": 0, "masked": 0, "escalated": 0},
        )
        status = alert.status.value
        if status == "BLOCKED":
            entry["blocked"] += 1
        elif status == "MASKED":
            entry["masked"] += 1
        elif status == "ESCALATED":
            entry["escalated"] += 1
    return sorted(
        counts.values(), key=lambda e: e["blocked"] + e["masked"] + e["escalated"], reverse=True
    )[:_TOP_N]


def _owasp_coverage(alerts: list[Alert]) -> list[OwaspCoverageRow]:
    rows = []
    for owasp_id, title in OWASP_CATALOG:
        events = sum(1 for alert in alerts if owasp_id in alert.owasp)
        rows.append(
            OwaspCoverageRow(
                id=owasp_id,
                title=title,
                events=events,
                status="covered" if events else "no events",
            )
        )
    return rows


def _recommendations(top_rules: list[dict], top_users: list[dict], stats_view: object) -> list[str]:
    recommendations: list[str] = []

    for user in top_users:
        if user["blocked"] >= _BLOCK_RECOMMENDATION_THRESHOLD:
            recommendations.append(
                f"{user['name']} ({user['sub']}) had {user['blocked']} blocked calls in this "
                "period; review their activity for repeated policy violations."
            )

    for rule in top_rules:
        if rule["count"] >= _RULE_RECOMMENDATION_THRESHOLD:
            recommendations.append(
                f"Rule '{rule['rule_id']}' fired {rule['count']} times in this period; "
                "consider tightening the control or investigating the root cause."
            )

    for budget_user in stats_view.budget.users:
        if budget_user.tokens_limit <= 0:
            continue
        percent = 100 * budget_user.tokens_used / budget_user.tokens_limit
        if percent >= _BUDGET_RECOMMENDATION_PERCENT:
            recommendations.append(
                f"{budget_user.name} ({budget_user.sub}) has used {percent:.0f}% of their "
                "token budget; consider a budget increase or usage review."
            )

    return recommendations


class SecurityReportUseCase:
    def __init__(
        self,
        stats_calculator: _ComputesStats,
        audit_repository: AuditRepository,
        alert_store: AlertStore,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._stats_calculator = stats_calculator
        self._audit_repository = audit_repository
        self._alert_store = alert_store
        self._clock = clock

    async def execute(self, period: str) -> ReportView:
        stats_view = await self._stats_calculator.compute()

        all_records = await load_all_call_records(self._audit_repository)
        records = filter_by_period(all_records, period, now=self._clock())
        allowed, blocked, masked, escalated, flagged, *_ = tally_call_records(records)
        total = len(records)

        all_alerts = await self._alert_store.list_recent(limit=_ALERT_OVERFETCH_LIMIT)
        alerts = filter_by_period(
            all_alerts, period, key=lambda a: a.created_at, now=self._clock()
        )

        top_rules = _tally_top_rules(alerts)
        top_users = _tally_top_users(alerts)
        owasp_coverage = _owasp_coverage(alerts)
        recommendations = _recommendations(top_rules, top_users, stats_view)

        summary = {
            "total_calls": total,
            "allowed": allowed,
            "blocked": blocked,
            "masked": masked,
            "escalated": escalated,
            "flagged": flagged,
            "posture_score": posture_score(total, allowed, masked),
            "cache_hit_ratio": stats_view.cache_hit_ratio,
            "policy": stats_view.policy.model_dump(),
        }

        generated_at = self._clock()
        markdown = render_markdown(
            generated_at=generated_at,
            period=period,
            summary=summary,
            top_rules=top_rules,
            top_users=top_users,
            owasp_coverage=owasp_coverage,
            recommendations=recommendations,
        )

        return ReportView(
            generated_at=generated_at,
            period=period,
            summary=summary,
            top_rules=top_rules,
            top_users=top_users,
            owasp_coverage=owasp_coverage,
            recommendations=recommendations,
            markdown=markdown,
        )
