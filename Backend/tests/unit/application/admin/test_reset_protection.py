from __future__ import annotations

from control_layer.application.services.protection_service import ProtectionService
from control_layer.application.telemetry.metrics_collector import MetricsCollector
from control_layer.application.use_cases.admin.reset import ResetDemoUseCase
from control_layer.domain.models.enums import ProtectionMode
from control_layer.infrastructure.cache.in_memory_cache_repository import InMemoryCacheRepository
from tests.unit.application.admin.test_reset import (
    FakeApprovalRepository,
    FakeAuditRepository,
    FakeBudgetRepository,
    FakeRiskRepository,
    FakeSessionRepository,
)


class _ClearLogs:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self) -> list[str]:
        self.calls += 1
        return []


async def test_full_reset_clears_logs_and_protection_state() -> None:
    cache = InMemoryCacheRepository()
    protection = ProtectionService(cache)
    await protection.set_mode(ProtectionMode.off)
    await protection.set_rule_override("pii_masking", False)
    audit, clear_logs = FakeAuditRepository(), _ClearLogs()

    use_case = ResetDemoUseCase(
        audit,
        object(),
        FakeBudgetRepository(),
        FakeSessionRepository(),
        FakeRiskRepository([]),
        FakeApprovalRepository([]),
        cache,
        MetricsCollector(),
        clear_logs=clear_logs,  # type: ignore[arg-type]
        protection=protection,
    )
    await use_case.execute()

    assert clear_logs.calls == 1
    assert audit.cleared is False
    assert await protection.get_mode() is ProtectionMode.enforce
    assert await protection.get_rule_overrides() == {}
