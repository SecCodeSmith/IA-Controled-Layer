from __future__ import annotations

from datetime import UTC, datetime

from control_layer.application.telemetry.metrics_collector import MetricsCollector
from control_layer.application.use_cases.admin.reset import ResetDemoUseCase
from control_layer.domain.models.approval import PendingApproval
from control_layer.domain.models.enums import ApprovalStatus, Role
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.risk import RiskProfile
from control_layer.domain.models.tool import ToolCallRequest


class FakeAuditRepository:
    def __init__(self) -> None:
        self.cleared = False

    async def clear(self) -> None:
        self.cleared = True


class FakeAlertStore:
    def __init__(self, *, with_clear: bool = True) -> None:
        self.cleared = False
        if with_clear:
            self.clear = self._clear

    async def _clear(self) -> None:
        self.cleared = True


class FakeBudgetRepository:
    def __init__(self) -> None:
        self.reset_calls: list[str | None] = []

    async def reset(self, sub: str | None = None) -> None:
        self.reset_calls.append(sub)


class FakeSessionRepository:
    def __init__(self) -> None:
        self.cleared_sessions: list[str | None] = []

    async def clear(self, session_id: str | None = None) -> None:
        self.cleared_sessions.append(session_id)


class FakeRiskRepository:
    def __init__(self, profiles: list[RiskProfile]) -> None:
        self._profiles = profiles
        self.updated: list[RiskProfile] = []

    async def list_all(self) -> list[RiskProfile]:
        return self._profiles

    async def update(self, profile: RiskProfile) -> None:
        self.updated.append(profile)


class FakeApprovalRepository:
    def __init__(self, pending: list[PendingApproval]) -> None:
        self._pending = pending
        self.updated: list[tuple[str, ApprovalStatus]] = []

    async def list_pending(self) -> list[PendingApproval]:
        return self._pending

    async def update_status(self, approval_id: str, status: ApprovalStatus) -> None:
        self.updated.append((approval_id, status))


class FakeCache:
    def __init__(self) -> None:
        self.flushed_prefixes: list[str] = []

    async def flush(self, prefix: str) -> None:
        self.flushed_prefixes.append(prefix)


def _approval(approval_id: str) -> PendingApproval:
    return PendingApproval(
        id=approval_id,
        identity=Identity(
            sub="anna.kowalska",
            name="Anna Kowalska",
            role=Role.developer,
            location="Krakow, PL",
            region="PL",
            agent_id="agent-1",
        ),
        tool_call=ToolCallRequest(server="github", tool="delete_branch"),
        created_at=datetime.now(UTC),
        rule_id="destructive_requires_approval",
        status=ApprovalStatus.pending,
    )


async def test_reset_clears_audit_budget_sessions_and_cache() -> None:
    audit = FakeAuditRepository()
    alerts = FakeAlertStore()
    budgets = FakeBudgetRepository()
    sessions = FakeSessionRepository()
    risks = FakeRiskRepository([])
    approvals = FakeApprovalRepository([])
    cache = FakeCache()
    metrics = MetricsCollector()
    metrics.record_cache(True)

    use_case = ResetDemoUseCase(audit, alerts, budgets, sessions, risks, approvals, cache, metrics)
    await use_case.execute()

    assert audit.cleared is True
    assert budgets.reset_calls == [None]
    assert sessions.cleared_sessions == [None]
    assert metrics.snapshot().cache.hits == 0
    expected_prefixes = {
        "decision:", "rate:", "loop:", "cb:", "quarantine:", "seen:", "calls:", "vault:"
    }
    assert set(cache.flushed_prefixes) == expected_prefixes


async def test_reset_clears_alerts_when_the_store_supports_it() -> None:
    audit = FakeAuditRepository()
    alerts = FakeAlertStore(with_clear=True)
    use_case = ResetDemoUseCase(
        audit,
        alerts,
        FakeBudgetRepository(),
        FakeSessionRepository(),
        FakeRiskRepository([]),
        FakeApprovalRepository([]),
        FakeCache(),
        MetricsCollector(),
    )

    await use_case.execute()

    assert alerts.cleared is True


async def test_reset_tolerates_an_alert_store_without_clear() -> None:
    audit = FakeAuditRepository()
    alerts = FakeAlertStore(with_clear=False)
    use_case = ResetDemoUseCase(
        audit,
        alerts,
        FakeBudgetRepository(),
        FakeSessionRepository(),
        FakeRiskRepository([]),
        FakeApprovalRepository([]),
        FakeCache(),
        MetricsCollector(),
    )

    await use_case.execute()  # must not raise


async def test_reset_zeroes_every_risk_profile() -> None:
    risks = FakeRiskRepository([RiskProfile(sub="anna.kowalska", score=40)])
    use_case = ResetDemoUseCase(
        FakeAuditRepository(),
        FakeAlertStore(),
        FakeBudgetRepository(),
        FakeSessionRepository(),
        risks,
        FakeApprovalRepository([]),
        FakeCache(),
        MetricsCollector(),
    )

    await use_case.execute()

    assert len(risks.updated) == 1
    assert risks.updated[0].sub == "anna.kowalska"
    assert risks.updated[0].score == 0


async def test_reset_expires_every_pending_approval() -> None:
    approvals = FakeApprovalRepository([_approval("ap_1"), _approval("ap_2")])
    use_case = ResetDemoUseCase(
        FakeAuditRepository(),
        FakeAlertStore(),
        FakeBudgetRepository(),
        FakeSessionRepository(),
        FakeRiskRepository([]),
        approvals,
        FakeCache(),
        MetricsCollector(),
    )

    await use_case.execute()

    assert approvals.updated == [("ap_1", ApprovalStatus.expired), ("ap_2", ApprovalStatus.expired)]
