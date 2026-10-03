from __future__ import annotations

import pytest

from control_layer.application.services.risk_service import RiskService
from control_layer.domain.models.decision import Decision
from control_layer.domain.models.enums import CallStatus, Role, RuleAction, Severity, StageName
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.risk import RiskProfile


class _FakeRiskRepository:
    def __init__(self) -> None:
        self._profiles: dict[str, RiskProfile] = {}

    async def get(self, sub: str) -> RiskProfile:
        return self._profiles.get(sub, RiskProfile(sub=sub))

    async def update(self, profile: RiskProfile) -> None:
        self._profiles[profile.sub] = profile

    async def list_all(self) -> list[RiskProfile]:
        return list(self._profiles.values())


def _identity() -> Identity:
    return Identity(
        sub="anna.kowalska",
        name="Anna Kowalska",
        role=Role.developer,
        location="Krakow, PL",
        region="PL",
        agent_id="agent-anna-dev-7f3a",
    )


def _decision(status: CallStatus, rule_id: str | None = None) -> Decision:
    from control_layer.domain.models.decision import Violation

    violations = []
    if rule_id is not None:
        violations.append(
            Violation(
                stage=StageName.policy,
                rule_id=rule_id,
                action=RuleAction.block,
                severity=Severity.high,
                owasp=[],
                evidence=[],
                confidence=1.0,
            )
        )
    return Decision(status=status, action=RuleAction.block, violations=violations)


@pytest.mark.parametrize(
    ("status", "expected_increment"),
    [
        (CallStatus.BLOCKED, 10),
        (CallStatus.ESCALATED, 5),
        (CallStatus.MASKED, 3),
        (CallStatus.FLAGGED, 3),
        (CallStatus.ALLOWED, 0),
    ],
)
async def test_score_increments_match_status(status: CallStatus, expected_increment: int) -> None:
    repo = _FakeRiskRepository()
    service = RiskService(repo)
    profile = await service.record(_identity(), _decision(status))
    assert profile.score == expected_increment


@pytest.mark.parametrize(
    ("score", "expected_level"),
    [
        (0, Severity.low),
        (24, Severity.low),
        (25, Severity.medium),
        (49, Severity.medium),
        (50, Severity.high),
        (74, Severity.high),
        (75, Severity.critical),
        (200, Severity.critical),
    ],
)
def test_level_for_boundaries(score: int, expected_level: Severity) -> None:
    from control_layer.application.services.risk_service import _level_for

    assert _level_for(score) == expected_level


async def test_record_persists_computed_level_on_profile() -> None:
    repo = _FakeRiskRepository()
    service = RiskService(repo)
    identity = _identity()
    for _ in range(3):
        await service.record(identity, _decision(CallStatus.BLOCKED))
    profile = await repo.get(identity.sub)
    assert profile.score == 30
    assert profile.level == Severity.medium


async def test_signals_keep_last_ten_rule_ids() -> None:
    repo = _FakeRiskRepository()
    service = RiskService(repo)
    identity = _identity()
    for i in range(12):
        await service.record(identity, _decision(CallStatus.BLOCKED, rule_id=f"rule_{i}"))
    profile = await repo.get(identity.sub)
    assert profile.signals == [f"rule_{i}" for i in range(2, 12)]
    assert len(profile.signals) == 10
