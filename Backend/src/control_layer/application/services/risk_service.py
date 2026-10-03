from __future__ import annotations

from control_layer.domain.models.decision import Decision
from control_layer.domain.models.enums import CallStatus, Severity
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.risk import RiskProfile
from control_layer.domain.ports.risk_repository import RiskRepository

_SCORE_BY_STATUS: dict[CallStatus, int] = {
    CallStatus.BLOCKED: 10,
    CallStatus.ESCALATED: 5,
    CallStatus.MASKED: 3,
    CallStatus.FLAGGED: 3,
    CallStatus.ALLOWED: 0,
}

_MAX_SIGNALS = 10


def _level_for(score: int) -> Severity:
    if score < 25:
        return Severity.low
    if score < 50:
        return Severity.medium
    if score < 75:
        return Severity.high
    return Severity.critical


class RiskService:
    def __init__(self, risk_repository: RiskRepository) -> None:
        self._risk_repository = risk_repository

    async def record(self, identity: Identity, decision: Decision) -> RiskProfile:
        profile = await self._risk_repository.get(identity.sub)
        score = profile.score + _SCORE_BY_STATUS.get(decision.status, 0)

        signals = list(profile.signals)
        primary = decision.primary_violation
        if primary is not None:
            signals.append(primary.rule_id)
        signals = signals[-_MAX_SIGNALS:]

        updated = RiskProfile(sub=identity.sub, score=score, level=_level_for(score), signals=signals)
        await self._risk_repository.update(updated)
        return updated
