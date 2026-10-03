from __future__ import annotations

from datetime import UTC, datetime

from control_layer.application.services.alert_factory import AlertFactory
from control_layer.application.services.audit_service import AuditService
from control_layer.domain.models.audit import (
    CallDecisionInfo,
    CallLatency,
    CallRecord,
    CallRequestInfo,
    CallResponseInfo,
    TokensInfo,
)
from control_layer.domain.models.decision import Decision, Violation
from control_layer.domain.models.enums import CallKind, CallStatus, Role, RuleAction, Severity, StageName
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.provider import ProviderInfo


class _FakeAuditRepository:
    def __init__(self) -> None:
        self.appended: list[CallRecord] = []

    async def append(self, record: CallRecord) -> None:
        self.appended.append(record)

    async def list_recent(self, limit: int = 100):  # noqa: ANN201
        return self.appended

    async def get(self, call_id: str):  # noqa: ANN201
        return next((r for r in self.appended if r.call_id == call_id), None)

    async def clear(self) -> None:
        self.appended.clear()

    async def export_rows(self):  # noqa: ANN201
        return []


class _FakeAlertSink:
    def __init__(self) -> None:
        self.emitted = []

    async def emit(self, alert) -> None:  # noqa: ANN001
        self.emitted.append(alert)


class _FakeAlertStore:
    def __init__(self) -> None:
        self.added = []

    async def add(self, alert) -> None:  # noqa: ANN001
        self.added.append(alert)

    async def list_recent(self, limit: int = 100):  # noqa: ANN201
        return self.added

    def subscribe(self):  # noqa: ANN201
        raise NotImplementedError

    async def clear(self) -> None:
        self.added.clear()


class _FakeEventPublisher:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []

    async def publish(self, event: str, data: dict) -> None:
        self.published.append((event, data))


class _FakePolicyRepository:
    async def current(self):  # noqa: ANN201
        raise NotImplementedError

    async def reload(self):  # noqa: ANN201
        raise NotImplementedError

    async def status(self) -> dict:
        return {}


def _identity() -> Identity:
    return Identity(
        sub="anna.kowalska",
        name="Anna Kowalska",
        role=Role.developer,
        location="Krakow, PL",
        region="PL",
        agent_id="agent-anna-dev-7f3a",
    )


def _call_record(status: CallStatus) -> CallRecord:
    return CallRecord(
        call_id="c_000001",
        timestamp=datetime(2026, 10, 3, 10, 0, tzinfo=UTC),
        identity=_identity(),
        kind=CallKind.tool_call,
        target="logs-db.query",
        decision=CallDecisionInfo(status=status, stage=StageName.dlp, rule_id="pii_masking"),
        request=CallRequestInfo(summary="s", payload={}),
        response=CallResponseInfo(raw="raw", delivered="delivered"),
        tokens=TokensInfo(),
        latency=CallLatency(proxy_ms=1.0, upstream_ms=2.0),
        provider=ProviderInfo(name="mock", model="mock"),
    )


def _service(audit_repo, alert_sink, alert_store, publisher):  # noqa: ANN001
    return AuditService(audit_repo, alert_sink, alert_store, publisher, AlertFactory(), _FakePolicyRepository())


async def test_record_appends_call_record() -> None:
    audit_repo = _FakeAuditRepository()
    service = _service(audit_repo, _FakeAlertSink(), _FakeAlertStore(), _FakeEventPublisher())
    call = _call_record(CallStatus.ALLOWED)
    await service.record(call, Decision(status=CallStatus.ALLOWED, action=RuleAction.allow))
    assert audit_repo.appended == [call]


async def test_record_returns_none_and_skips_alert_for_allowed() -> None:
    alert_sink, alert_store = _FakeAlertSink(), _FakeAlertStore()
    service = _service(_FakeAuditRepository(), alert_sink, alert_store, _FakeEventPublisher())
    alert = await service.record(
        _call_record(CallStatus.ALLOWED), Decision(status=CallStatus.ALLOWED, action=RuleAction.allow)
    )
    assert alert is None
    assert alert_sink.emitted == []
    assert alert_store.added == []


async def test_record_emits_and_stores_alert_for_non_allowed() -> None:
    alert_sink, alert_store = _FakeAlertSink(), _FakeAlertStore()
    service = _service(_FakeAuditRepository(), alert_sink, alert_store, _FakeEventPublisher())
    violation = Violation(
        stage=StageName.dlp,
        rule_id="pii_masking",
        action=RuleAction.mask,
        severity=Severity.medium,
        owasp=["LLM02"],
        evidence=[],
        confidence=1.0,
    )
    decision = Decision(status=CallStatus.MASKED, action=RuleAction.mask, violations=[violation])
    alert = await service.record(_call_record(CallStatus.MASKED), decision)
    assert alert is not None
    assert alert_sink.emitted == [alert]
    assert alert_store.added == [alert]


async def test_record_publishes_feed_alert_and_stats_dirty_events() -> None:
    publisher = _FakeEventPublisher()
    service = _service(_FakeAuditRepository(), _FakeAlertSink(), _FakeAlertStore(), publisher)
    violation = Violation(
        stage=StageName.dlp,
        rule_id="pii_masking",
        action=RuleAction.mask,
        severity=Severity.medium,
        owasp=[],
        evidence=[],
        confidence=1.0,
    )
    decision = Decision(status=CallStatus.MASKED, action=RuleAction.mask, violations=[violation])
    await service.record(_call_record(CallStatus.MASKED), decision)
    events = [name for name, _ in publisher.published]
    assert events == ["feed", "alert", "stats_dirty"]


async def test_record_skips_alert_event_when_allowed() -> None:
    publisher = _FakeEventPublisher()
    service = _service(_FakeAuditRepository(), _FakeAlertSink(), _FakeAlertStore(), publisher)
    await service.record(
        _call_record(CallStatus.ALLOWED), Decision(status=CallStatus.ALLOWED, action=RuleAction.allow)
    )
    events = [name for name, _ in publisher.published]
    assert events == ["feed", "stats_dirty"]


async def test_feed_event_payload_shape() -> None:
    publisher = _FakeEventPublisher()
    service = _service(_FakeAuditRepository(), _FakeAlertSink(), _FakeAlertStore(), publisher)
    await service.record(
        _call_record(CallStatus.ALLOWED), Decision(status=CallStatus.ALLOWED, action=RuleAction.allow)
    )
    _, feed_payload = publisher.published[0]
    assert feed_payload["call_id"] == "c_000001"
    assert feed_payload["user"] == {"sub": "anna.kowalska", "name": "Anna Kowalska", "role": "developer"}
    assert feed_payload["kind"] == "tool_call"
    assert feed_payload["target"] == "logs-db.query"
    assert feed_payload["status"] == "ALLOWED"
