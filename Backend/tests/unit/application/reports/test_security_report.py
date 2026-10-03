from __future__ import annotations

from datetime import UTC, datetime, timedelta

from control_layer.application.reports.security_report import SecurityReportUseCase
from control_layer.application.use_cases.admin.stats import (
    BudgetStats,
    BudgetUserStat,
    LatencyStats,
    PolicyStatusRef,
    StatsView,
)
from control_layer.domain.models.alert import Alert, AlertUserRef
from control_layer.domain.models.audit import (
    CallDecisionInfo,
    CallLatency,
    CallRecord,
    CallRequestInfo,
    CallResponseInfo,
    TokensInfo,
)
from control_layer.domain.models.enums import CallKind, CallStatus, Role, Severity, StageName
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.provider import ProviderInfo

NOW = datetime(2026, 10, 3, 12, 0, 0, tzinfo=UTC)


def _identity(sub: str, name: str) -> Identity:
    return Identity(
        sub=sub,
        name=name,
        role=Role.developer,
        location="Krakow, PL",
        region="PL",
        agent_id="agent-1",
    )


def _record(
    call_id: str,
    *,
    sub: str = "anna.kowalska",
    name: str = "Anna Kowalska",
    status: CallStatus = CallStatus.BLOCKED,
    age: timedelta = timedelta(minutes=1),
) -> CallRecord:
    return CallRecord(
        call_id=call_id,
        timestamp=NOW - age,
        identity=_identity(sub, name),
        kind=CallKind.chat,
        target="llm.complete",
        decision=CallDecisionInfo(status=status),
        request=CallRequestInfo(summary="prompt"),
        response=CallResponseInfo(raw="hi", delivered="hi"),
        tokens=TokensInfo(prompt=1, completion=1, total=2),
        latency=CallLatency(proxy_ms=1.0, upstream_ms=1.0, stages={}),
        provider=ProviderInfo(name="mock", model="mock"),
    )


def _alert(
    alert_id: str,
    *,
    sub: str = "anna.kowalska",
    name: str = "Anna Kowalska",
    status: CallStatus = CallStatus.BLOCKED,
    stage: StageName = StageName.policy,
    rule_id: str | None = "prompt_injection_signatures",
    owasp: list[str] | None = None,
    age: timedelta = timedelta(minutes=1),
) -> Alert:
    return Alert(
        id=alert_id,
        created_at=NOW - age,
        call_id=f"c_{alert_id}",
        user=AlertUserRef(sub=sub, name=name, role=Role.developer),
        status=status,
        stage=stage,
        rule_id=rule_id,
        severity=Severity.medium,
        owasp=owasp or ["LLM01", "ASI01"],
        reason="blocked",
    )


class FakeAuditRepository:
    def __init__(self, records: list[CallRecord]) -> None:
        self._records = records

    async def export_rows(self) -> list[dict]:
        return [r.model_dump(mode="json") for r in self._records]


class FakeAlertStore:
    def __init__(self, alerts: list[Alert]) -> None:
        self._alerts = alerts

    async def list_recent(self, limit: int = 100) -> list[Alert]:
        return self._alerts[-limit:]


def _stats_view(budget_users: list[BudgetUserStat] | None = None) -> StatsView:
    return StatsView(
        total_calls=10,
        allowed=5,
        blocked=3,
        masked=1,
        escalated=1,
        flagged=0,
        budget=BudgetStats(users=budget_users or []),
        posture_score=70,
        cache_hit_ratio=0.5,
        latency=LatencyStats(
            proxy_p50_ms=1.0, proxy_p95_ms=2.0, upstream_p50_ms=3.0, upstream_p95_ms=4.0
        ),
        provider=ProviderInfo(name="mock", model="mock"),
        policy=PolicyStatusRef(version=3, status="LOADED"),
    )


class FakeStatsCalculator:
    def __init__(self, view: StatsView) -> None:
        self._view = view

    async def compute(self) -> StatsView:
        return self._view


def _clock() -> datetime:
    return NOW


def _use_case(
    records: list[CallRecord] | None = None,
    alerts: list[Alert] | None = None,
    stats_view: StatsView | None = None,
) -> SecurityReportUseCase:
    return SecurityReportUseCase(
        FakeStatsCalculator(stats_view or _stats_view()),
        FakeAuditRepository(records or []),
        FakeAlertStore(alerts or []),
        clock=_clock,
    )


async def test_summary_counts_recompute_from_period_filtered_audit_records() -> None:
    records = [
        _record("c_1", status=CallStatus.ALLOWED),
        _record("c_2", status=CallStatus.BLOCKED),
        _record("c_3", status=CallStatus.MASKED),
    ]
    use_case = _use_case(records=records)

    report = await use_case.execute("all")

    assert report.summary["total_calls"] == 3
    assert report.summary["allowed"] == 1
    assert report.summary["blocked"] == 1
    assert report.summary["masked"] == 1
    assert report.summary["posture_score"] == 67


async def test_summary_carries_live_cache_hit_ratio_and_policy_from_stats() -> None:
    use_case = _use_case()

    report = await use_case.execute("all")

    assert report.summary["cache_hit_ratio"] == 0.5
    assert report.summary["policy"]["version"] == 3


async def test_top_rules_counts_and_sorts_descending() -> None:
    alerts = [
        _alert("a1", rule_id="prompt_injection_signatures", stage=StageName.policy),
        _alert("a2", rule_id="prompt_injection_signatures", stage=StageName.policy),
        _alert("a3", rule_id="pii_masking", stage=StageName.dlp, status=CallStatus.MASKED),
    ]
    use_case = _use_case(alerts=alerts)

    report = await use_case.execute("all")

    assert report.top_rules[0]["rule_id"] == "prompt_injection_signatures"
    assert report.top_rules[0]["count"] == 2
    assert report.top_rules[0]["stage"] == "policy"


async def test_top_rules_skips_alerts_with_no_rule_id() -> None:
    alerts = [_alert("a1", rule_id=None)]
    use_case = _use_case(alerts=alerts)

    report = await use_case.execute("all")

    assert report.top_rules == []


async def test_top_users_tallies_blocked_masked_escalated() -> None:
    alerts = [
        _alert("a1", sub="anna.kowalska", name="Anna Kowalska", status=CallStatus.BLOCKED),
        _alert("a2", sub="anna.kowalska", name="Anna Kowalska", status=CallStatus.MASKED),
        _alert("a3", sub="anna.kowalska", name="Anna Kowalska", status=CallStatus.ESCALATED),
    ]
    use_case = _use_case(alerts=alerts)

    report = await use_case.execute("all")

    user_row = next(u for u in report.top_users if u["sub"] == "anna.kowalska")
    assert user_row["blocked"] == 1
    assert user_row["masked"] == 1
    assert user_row["escalated"] == 1


async def test_owasp_coverage_has_twenty_rows_in_catalog_order() -> None:
    alerts = [_alert("a1", owasp=["LLM01"])]
    use_case = _use_case(alerts=alerts)

    report = await use_case.execute("all")

    assert [row.id for row in report.owasp_coverage][:3] == ["LLM01", "LLM02", "LLM03"]
    assert len(report.owasp_coverage) == 20
    llm01 = next(row for row in report.owasp_coverage if row.id == "LLM01")
    llm08 = next(row for row in report.owasp_coverage if row.id == "LLM08")
    assert llm01.events == 1
    assert llm01.status == "covered"
    assert llm08.events == 0
    assert llm08.status == "no events"


async def test_recommendation_for_a_user_with_three_or_more_blocks() -> None:
    alerts = [_alert(f"a{i}", sub="anna.kowalska", status=CallStatus.BLOCKED) for i in range(3)]
    use_case = _use_case(alerts=alerts)

    report = await use_case.execute("all")

    assert any("Anna Kowalska" in r for r in report.recommendations)


async def test_recommendation_for_a_rule_firing_ten_or_more_times() -> None:
    alerts = [_alert(f"a{i}", rule_id="rate_limit") for i in range(10)]
    use_case = _use_case(alerts=alerts)

    report = await use_case.execute("all")

    assert any("rate_limit" in r for r in report.recommendations)


async def test_recommendation_for_a_user_near_their_budget() -> None:
    budget_users = [
        BudgetUserStat(
            sub="anna.kowalska",
            name="Anna Kowalska",
            tokens_used=8500,
            tokens_limit=10000,
            cost_used_usd=0.5,
        )
    ]
    use_case = _use_case(stats_view=_stats_view(budget_users))

    report = await use_case.execute("all")

    assert any("budget" in r.lower() for r in report.recommendations)


async def test_period_filter_excludes_calls_and_alerts_outside_the_window() -> None:
    records = [
        _record("c_old", age=timedelta(days=10)),
        _record("c_recent", age=timedelta(hours=1)),
    ]
    alerts = [
        _alert("a_old", age=timedelta(days=10)),
        _alert("a_recent", age=timedelta(hours=1)),
    ]
    use_case = _use_case(records=records, alerts=alerts)

    report_24h = await use_case.execute("24h")
    report_all = await use_case.execute("all")

    assert report_24h.summary["total_calls"] == 1
    assert report_all.summary["total_calls"] == 2
    assert sum(row["count"] for row in report_24h.top_rules) == 1
    assert sum(row["count"] for row in report_all.top_rules) == 2


async def test_markdown_contains_the_expected_headings() -> None:
    use_case = _use_case(records=[_record("c_1")], alerts=[_alert("a1")])

    report = await use_case.execute("all")

    assert report.markdown.startswith("# Security report")
    for heading in (
        "## Summary",
        "## Top rules",
        "## Top users",
        "## OWASP coverage",
        "## Recommendations",
    ):
        assert heading in report.markdown
