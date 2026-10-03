from __future__ import annotations

from datetime import UTC, datetime

from control_layer.application.services.alert_factory import AlertFactory
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


def _identity() -> Identity:
    return Identity(
        sub="anna.kowalska",
        name="Anna Kowalska",
        role=Role.developer,
        location="Krakow, PL",
        region="PL",
        agent_id="agent-anna-dev-7f3a",
    )


def _call_record(status: CallStatus, stage=None, rule_id=None, reason=None) -> CallRecord:  # noqa: ANN001
    return CallRecord(
        call_id="c_000001",
        timestamp=datetime(2026, 10, 3, 10, 0, tzinfo=UTC),
        identity=_identity(),
        kind=CallKind.tool_call,
        target="logs-db.query",
        decision=CallDecisionInfo(status=status, stage=stage, rule_id=rule_id, reason=reason),
        request=CallRequestInfo(summary="s", payload={}),
        response=CallResponseInfo(raw="raw", delivered="delivered"),
        tokens=TokensInfo(),
        latency=CallLatency(proxy_ms=1.0, upstream_ms=2.0),
        provider=ProviderInfo(name="mock", model="mock"),
    )


def _violation(action=RuleAction.block, severity=Severity.high, rule_id="role_provisioning"):  # noqa: ANN001
    return Violation(
        stage=StageName.authorization,
        rule_id=rule_id,
        action=action,
        severity=severity,
        owasp=["ASI03"],
        evidence=["github.delete_branch"],
        confidence=1.0,
        reason="not provisioned",
    )


def test_returns_none_for_allowed_decision() -> None:
    factory = AlertFactory()
    decision = Decision(status=CallStatus.ALLOWED, action=RuleAction.allow)
    assert factory.build(_call_record(CallStatus.ALLOWED), decision) is None


def test_builds_alert_with_severity_from_primary_violation() -> None:
    factory = AlertFactory()
    violation = _violation(severity=Severity.critical)
    decision = Decision(status=CallStatus.BLOCKED, action=RuleAction.block, violations=[violation])
    alert = factory.build(_call_record(CallStatus.BLOCKED), decision)
    assert alert is not None
    assert alert.severity == Severity.critical
    assert alert.rule_id == "role_provisioning"
    assert alert.user.sub == "anna.kowalska"
    assert alert.id.startswith("al_")


def test_rule_id_is_none_for_structural_block_without_violation() -> None:
    factory = AlertFactory()
    decision = Decision(status=CallStatus.BLOCKED, action=RuleAction.block, violations=[])
    call = _call_record(CallStatus.BLOCKED, stage=StageName.resource, reason="Token budget overrun")
    alert = factory.build(call, decision)
    assert alert is not None
    assert alert.rule_id is None
    assert alert.stage == StageName.resource
    assert alert.reason == "Token budget overrun"
