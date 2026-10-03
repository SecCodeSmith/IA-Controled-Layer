from __future__ import annotations

from datetime import UTC, datetime

from control_layer.application.telemetry.metrics_collector import (
    CacheMetric,
    LatencyBand,
    MetricsView,
    StageMetric,
)
from control_layer.application.use_cases.admin.stats import StatsCalculator
from control_layer.domain.models.audit import (
    CallDecisionInfo,
    CallLatency,
    CallRecord,
    CallRequestInfo,
    CallResponseInfo,
    TokensInfo,
)
from control_layer.domain.models.budget_usage import BudgetUsage
from control_layer.domain.models.enums import CallKind, CallStatus, Role, Severity, StageName
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.provider import ProviderInfo
from control_layer.domain.models.risk import RiskProfile


class _User:
    def __init__(self, sub: str, name: str) -> None:
        self.sub = sub
        self.name = name


def _identity(sub: str, role: Role = Role.developer) -> Identity:
    names = {"anna.kowalska": "Anna Kowalska", "marek.nowak": "Marek Nowak"}
    return Identity(
        sub=sub,
        name=names.get(sub, sub),
        role=role,
        location="Krakow, PL",
        region="PL",
        agent_id="agent-1",
    )


def _record(
    call_id: str,
    *,
    sub: str = "anna.kowalska",
    role: Role = Role.developer,
    status: CallStatus = CallStatus.ALLOWED,
    stage: StageName | None = None,
    rule_id: str | None = None,
    owasp: list[str] | None = None,
) -> CallRecord:
    return CallRecord(
        call_id=call_id,
        timestamp=datetime.now(UTC),
        identity=_identity(sub, role),
        kind=CallKind.chat,
        target="llm.complete",
        decision=CallDecisionInfo(status=status, stage=stage, rule_id=rule_id, owasp=owasp or []),
        request=CallRequestInfo(summary="prompt"),
        response=CallResponseInfo(raw="hi", delivered="hi"),
        tokens=TokensInfo(prompt=1, completion=1, total=2),
        latency=CallLatency(proxy_ms=1.0, upstream_ms=1.0, stages={}),
        provider=ProviderInfo(name="mock", model="mock"),
    )


class FakeAuditRepository:
    def __init__(self, records: list[CallRecord]) -> None:
        self._records = records

    async def export_rows(self) -> list[dict]:
        return [r.model_dump(mode="json") for r in self._records]


class FakeBudgetRepository:
    def __init__(self, usage: dict[str, BudgetUsage]) -> None:
        self._usage = usage

    async def get_usage(self, sub: str) -> BudgetUsage:
        return self._usage.get(
            sub,
            BudgetUsage(
                tokens_used=0,
                tokens_limit=10000,
                cost_used_usd=0.0,
                cost_limit_usd=1.0,
                resets_at=datetime.now(UTC),
            ),
        )


class FakeRiskRepository:
    def __init__(self, profiles: list[RiskProfile]) -> None:
        self._profiles = profiles

    async def list_all(self) -> list[RiskProfile]:
        return self._profiles


class FakePolicyRepository:
    async def status(self) -> dict:
        return {"version": 3, "status": "LOADED"}


class FakeModelProvider:
    def describe(self) -> ProviderInfo:
        return ProviderInfo(name="ollama", model="qwen2.5:7b")


class FakeUserRepository:
    def __init__(self, users: list[_User]) -> None:
        self._users = users

    async def list_all(self) -> list[_User]:
        return self._users


class FakeMetricsCollector:
    def __init__(self, hit_ratio: float = 0.5) -> None:
        self._hit_ratio = hit_ratio

    def snapshot(self) -> MetricsView:
        return MetricsView(
            stages={"dlp": StageMetric(p50_ms=1.0, p95_ms=2.0, count=1)},
            proxy=LatencyBand(p50_ms=3.0, p95_ms=9.0),
            upstream=LatencyBand(p50_ms=600.0, p95_ms=2000.0),
            overhead=LatencyBand(p50_ms=2.5, p95_ms=7.0),
            cache=CacheMetric(hits=1, misses=1, hit_ratio=self._hit_ratio),
            calls_per_minute=5.0,
        )


def _calculator(
    records: list[CallRecord],
    *,
    users: list[_User] | None = None,
    budgets: dict[str, BudgetUsage] | None = None,
    risks: list[RiskProfile] | None = None,
) -> StatsCalculator:
    return StatsCalculator(
        audit_repository=FakeAuditRepository(records),
        budget_repository=FakeBudgetRepository(budgets or {}),
        risk_repository=FakeRiskRepository(risks or []),
        metrics_collector=FakeMetricsCollector(),
        policy_repository=FakePolicyRepository(),
        model_provider=FakeModelProvider(),
        user_repository=FakeUserRepository(users or []),
    )


async def test_counts_by_status() -> None:
    records = [
        _record("c_1", status=CallStatus.ALLOWED),
        _record("c_2", status=CallStatus.BLOCKED),
        _record("c_3", status=CallStatus.MASKED),
        _record("c_4", status=CallStatus.ESCALATED),
    ]
    calculator = _calculator(records)

    stats = await calculator.compute()

    assert stats.total_calls == 4
    assert stats.allowed == 1
    assert stats.blocked == 1
    assert stats.masked == 1
    assert stats.escalated == 1
    assert stats.flagged == 0


async def test_by_stage_rule_owasp_and_role() -> None:
    records = [
        _record(
            "c_1",
            status=CallStatus.MASKED,
            stage=StageName.dlp,
            rule_id="pii_masking",
            owasp=["LLM02"],
        ),
        _record(
            "c_2",
            status=CallStatus.BLOCKED,
            stage=StageName.authorization,
            rule_id="role_provisioning",
            owasp=["ASI03", "LLM06"],
            role=Role.hr,
        ),
    ]
    calculator = _calculator(records)

    stats = await calculator.compute()

    assert stats.by_stage == {"dlp": 1, "authorization": 1}
    assert stats.by_rule == {"pii_masking": 1, "role_provisioning": 1}
    assert stats.by_owasp == {"LLM02": 1, "ASI03": 1, "LLM06": 1}
    assert stats.by_role == {"developer": 1, "hr": 1}


async def test_posture_score_rounds_allowed_or_masked_over_total() -> None:
    records = [
        _record("c_1", status=CallStatus.ALLOWED),
        _record("c_2", status=CallStatus.MASKED),
        _record("c_3", status=CallStatus.BLOCKED),
        _record("c_4", status=CallStatus.BLOCKED),
    ]
    calculator = _calculator(records)

    stats = await calculator.compute()

    assert stats.posture_score == 50


async def test_posture_score_is_100_when_no_calls() -> None:
    calculator = _calculator([])

    stats = await calculator.compute()

    assert stats.posture_score == 100


async def test_cache_hit_ratio_comes_from_metrics_collector() -> None:
    calculator = _calculator([])

    stats = await calculator.compute()

    assert stats.cache_hit_ratio == 0.5


async def test_latency_comes_from_metrics_snapshot() -> None:
    calculator = _calculator([])

    stats = await calculator.compute()

    assert stats.latency.proxy_p50_ms == 3.0
    assert stats.latency.proxy_p95_ms == 9.0
    assert stats.latency.upstream_p50_ms == 600.0
    assert stats.latency.overhead_p50_ms == 2.5
    assert stats.latency.overhead_p95_ms == 7.0
    assert stats.latency.upstream_p95_ms == 2000.0


async def test_provider_and_policy_come_from_their_ports() -> None:
    calculator = _calculator([])

    stats = await calculator.compute()

    assert stats.provider.name == "ollama"
    assert stats.provider.model == "qwen2.5:7b"
    assert stats.policy.version == 3
    assert stats.policy.status == "LOADED"


async def test_budget_users_resolve_names_from_user_repository() -> None:
    users = [_User("anna.kowalska", "Anna Kowalska")]
    budgets = {
        "anna.kowalska": BudgetUsage(
            tokens_used=3420,
            tokens_limit=10000,
            cost_used_usd=0.0012,
            cost_limit_usd=1.0,
            resets_at=datetime.now(UTC),
        )
    }
    calculator = _calculator([], users=users, budgets=budgets)

    stats = await calculator.compute()

    assert len(stats.budget.users) == 1
    user_stat = stats.budget.users[0]
    assert user_stat.sub == "anna.kowalska"
    assert user_stat.name == "Anna Kowalska"
    assert user_stat.tokens_used == 3420
    assert user_stat.tokens_limit == 10000


async def test_risk_list_resolves_names_from_user_repository() -> None:
    users = [_User("anna.kowalska", "Anna Kowalska")]
    risks = [RiskProfile(sub="anna.kowalska", score=12, level=Severity.low)]
    calculator = _calculator([], users=users, risks=risks)

    stats = await calculator.compute()

    assert len(stats.risk) == 1
    assert stats.risk[0].sub == "anna.kowalska"
    assert stats.risk[0].name == "Anna Kowalska"
    assert stats.risk[0].score == 12
    assert stats.risk[0].level == "low"
