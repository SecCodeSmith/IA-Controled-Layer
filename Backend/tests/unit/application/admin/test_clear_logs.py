from __future__ import annotations

import pytest

from control_layer.application.services.protection_service import ProtectionService
from control_layer.application.telemetry.metrics_collector import MetricsCollector
from control_layer.application.use_cases.admin.clear_logs import ClearLogsUseCase
from control_layer.application.use_cases.admin.protection import ManageProtectionUseCase
from control_layer.domain.exceptions import RuleNotFoundError
from control_layer.domain.models.enums import ProtectionMode
from control_layer.infrastructure.cache.in_memory_cache_repository import InMemoryCacheRepository
from tests.unit.application.policy.test_overridden_policy_repository import _InnerRepository


class _Audit:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    async def clear(self) -> None:
        self.rows = []

    async def export_rows(self) -> list[dict]:
        return self.rows


class _Clearable:
    def __init__(self) -> None:
        self.cleared = 0

    async def clear(self) -> None:
        self.cleared += 1


class _CallIds:
    def __init__(self) -> None:
        self.value: int | None = None

    async def reset(self, value: int) -> None:
        self.value = value


async def test_clear_logs_empties_every_store_and_reports_the_targets() -> None:
    audit = _Audit([{"call_id": "c_000007"}])
    store, sink, call_ids = _Clearable(), _Clearable(), _CallIds()
    metrics = MetricsCollector()
    metrics.record_cache(True)
    published: list[tuple[str, dict]] = []

    async def publish(event: str, data: dict) -> None:
        published.append((event, data))

    use_case = ClearLogsUseCase(audit, store, sink, metrics, call_ids, publish)  # type: ignore[arg-type]

    cleared = await use_case.execute()

    assert cleared == ["audit", "alerts", "alerts_xlsx", "audit_jsonl", "metrics", "feed"]
    assert audit.rows == []
    assert (store.cleared, sink.cleared) == (1, 1)
    assert metrics.snapshot().cache.hits == 0
    assert call_ids.value == 0
    assert published == [("stats_dirty", {})]


def _manage() -> tuple[ManageProtectionUseCase, ProtectionService]:
    protection = ProtectionService(InMemoryCacheRepository())
    return ManageProtectionUseCase(protection, _InnerRepository()), protection  # type: ignore[arg-type]


async def test_manage_protection_set_mode_and_rule_round_trip() -> None:
    manage, _ = _manage()

    view = await manage.set_mode(ProtectionMode.monitor)
    override = await manage.set_rule("pii_masking", False)

    assert view.mode is ProtectionMode.monitor
    assert (override.rule_id, override.enabled, override.overridden) == ("pii_masking", False, True)
    assert (await manage.get()).rule_overrides == {"pii_masking": False}


async def test_manage_protection_rejects_unknown_rules() -> None:
    manage, _ = _manage()

    with pytest.raises(RuleNotFoundError):
        await manage.set_rule("ghost", False)


async def test_manage_protection_clear_overrides_keeps_mode() -> None:
    manage, _ = _manage()
    await manage.set_mode(ProtectionMode.off)
    await manage.set_rule("pii_masking", False)

    view = await manage.clear_overrides()

    assert view.rule_overrides == {}
    assert view.mode is ProtectionMode.off
