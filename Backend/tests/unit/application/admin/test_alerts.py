from __future__ import annotations

from datetime import UTC, datetime

from control_layer.application.use_cases.admin.alerts import ListAlertsUseCase
from control_layer.domain.models.alert import Alert, AlertUserRef
from control_layer.domain.models.enums import CallStatus, Role, Severity, StageName


def _alert(alert_id: str, sub: str = "anna.kowalska", rule_id: str = "pii_masking") -> Alert:
    return Alert(
        id=alert_id,
        created_at=datetime.now(UTC),
        call_id=f"c_{alert_id}",
        user=AlertUserRef(sub=sub, name="Anna Kowalska", role=Role.developer),
        status=CallStatus.MASKED,
        stage=StageName.dlp,
        rule_id=rule_id,
        severity=Severity.medium,
        reason="3 emails masked",
    )


class FakeAlertStore:
    def __init__(self, alerts: list[Alert]) -> None:
        self._alerts = alerts

    async def add(self, alert: Alert) -> None:
        self._alerts.append(alert)

    async def list_recent(self, limit: int = 100) -> list[Alert]:
        return self._alerts[-limit:]

    def subscribe(self):
        raise NotImplementedError


async def test_list_alerts_returns_recent_alerts() -> None:
    store = FakeAlertStore([_alert("1"), _alert("2")])
    use_case = ListAlertsUseCase(store)

    result = await use_case.execute(limit=100, user=None, rule_id=None)

    assert [a.id for a in result] == ["1", "2"]


async def test_list_alerts_filters_by_user() -> None:
    store = FakeAlertStore([_alert("1", sub="anna.kowalska"), _alert("2", sub="marek.nowak")])
    use_case = ListAlertsUseCase(store)

    result = await use_case.execute(limit=100, user="marek.nowak", rule_id=None)

    assert [a.id for a in result] == ["2"]


async def test_list_alerts_filters_by_rule_id() -> None:
    store = FakeAlertStore([_alert("1", rule_id="pii_masking"), _alert("2", rule_id="rate_limit")])
    use_case = ListAlertsUseCase(store)

    result = await use_case.execute(limit=100, user=None, rule_id="rate_limit")

    assert [a.id for a in result] == ["2"]
