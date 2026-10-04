from __future__ import annotations

from datetime import UTC, datetime

import pytest

from control_layer.application.services.admin_action_recorder import AdminActionRecorder
from control_layer.application.services.alert_factory import AlertFactory
from control_layer.application.services.audit_service import AuditService
from control_layer.application.services.call_id_generator import CallIdGenerator
from control_layer.domain.models.enums import CallKind, CallStatus, Role
from control_layer.infrastructure.cache.in_memory_cache_repository import InMemoryCacheRepository

_NOW = datetime(2026, 10, 4, 9, 0, tzinfo=UTC)


class _Repo:
    def __init__(self) -> None:
        self.rows = []

    async def append(self, record) -> None:  # noqa: ANN001
        self.rows.append(record)


class _Collect:
    def __init__(self) -> None:
        self.items = []

    async def emit(self, alert) -> None:  # noqa: ANN001
        self.items.append(alert)

    add = emit


class _Publisher:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def publish(self, event: str, data: dict) -> None:
        self.events.append((event, data))


def _recorder() -> tuple[AdminActionRecorder, _Repo, _Collect, _Publisher]:
    repo, alerts, publisher = _Repo(), _Collect(), _Publisher()
    audit = AuditService(repo, alerts, alerts, publisher, AlertFactory(), None)  # type: ignore[arg-type]
    recorder = AdminActionRecorder(audit, CallIdGenerator(InMemoryCacheRepository()), lambda: _NOW)
    return recorder, repo, alerts, publisher


@pytest.mark.parametrize(
    ("action", "reason", "loosening"),
    [
        ("admin.protection", "protection mode set to off (was enforce)", True),
        ("admin.rule_override", "rule pii_masking disabled", True),
        ("admin.model", "model switched to gemma4:latest (not allowlisted)", True),
        ("admin.logs", "logs cleared", True),
        ("admin.reset", "demo reset (scope=all)", True),
        ("admin.protection", "protection mode set to enforce (was off)", False),
        ("admin.policy_reload", "policy reloaded", False),
    ],
)
async def test_record_builds_expected_call_record(
    action: str, reason: str, loosening: bool
) -> None:
    recorder, repo, alerts, publisher = _recorder()

    call = await recorder.record(action, details={"reason": reason}, loosening=loosening)

    assert repo.rows == [call]
    assert call.kind is CallKind.admin
    assert call.target == action
    assert call.decision.reason == reason
    assert call.decision.status is (CallStatus.FLAGGED if loosening else CallStatus.ALLOWED)
    assert call.identity.sub == "admin"
    assert call.identity.name == "Administrator"
    assert call.identity.role is Role.admin
    assert call.identity.agent_id == "admin-console"
    assert call.timestamp == _NOW
    assert call.tokens.total == 0
    assert call.latency.proxy_ms == 0.0
    assert call.response.raw is None
    assert call.request.summary == reason
    assert [name for name, _ in publisher.events if name == "feed"] == ["feed"]
    assert len(alerts.items) == (2 if loosening else 0)
    if loosening:
        assert reason in alerts.items[0].reason
        assert alerts.items[0].rule_id == action


async def test_record_uses_given_actor_and_sequential_ids() -> None:
    recorder, _, _, _ = _recorder()

    first = await recorder.record("admin.logs", details={"reason": "x"}, loosening=False)
    second = await recorder.record(
        "admin.logs", details={"reason": "y"}, loosening=False, actor="ops"
    )

    assert (first.call_id, second.call_id) == ("c_000001", "c_000002")
    assert second.identity.sub == "ops"
