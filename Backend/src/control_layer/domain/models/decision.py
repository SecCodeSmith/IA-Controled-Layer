from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from control_layer.domain.models.enums import CallStatus, RuleAction, Severity, StageName

_PRECEDENCE: tuple[RuleAction, ...] = (
    RuleAction.quarantine,
    RuleAction.block,
    RuleAction.require_approval,
    RuleAction.mask,
    RuleAction.flag,
    RuleAction.allow,
)

_STATUS_BY_ACTION: dict[RuleAction, CallStatus] = {
    RuleAction.quarantine: CallStatus.BLOCKED,
    RuleAction.block: CallStatus.BLOCKED,
    RuleAction.require_approval: CallStatus.ESCALATED,
    RuleAction.mask: CallStatus.MASKED,
    RuleAction.flag: CallStatus.FLAGGED,
    RuleAction.allow: CallStatus.ALLOWED,
}


def merge_action(actions: list[RuleAction]) -> RuleAction:
    for candidate in _PRECEDENCE:
        if candidate in actions:
            return candidate
    return RuleAction.allow


def status_for(action: RuleAction) -> CallStatus:
    return _STATUS_BY_ACTION[action]


def pick_primary_violation(violations: list[Violation]) -> Violation | None:
    if not violations:
        return None
    for candidate in _PRECEDENCE:
        for violation in violations:
            if violation.action == candidate:
                return violation
    return None


class RuleOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    matched: bool
    confidence: float = 1.0
    evidence: list[str] = Field(default_factory=list)
    masked_text: str | None = None
    inconclusive: bool = False
    reason: str | None = None


class Violation(BaseModel):
    model_config = ConfigDict(frozen=True)

    stage: StageName
    rule_id: str
    action: RuleAction
    severity: Severity
    owasp: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    reason: str | None = None


class StageResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    stage: StageName
    action: RuleAction
    violations: list[Violation] = Field(default_factory=list)
    masked_text: str | None = None
    approval_id: str | None = None
    timing_ms: float
    cache_hit: bool = False
    reason: str | None = None


class Decision(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: CallStatus
    action: RuleAction
    violations: list[Violation] = Field(default_factory=list)
    masked_text: str | None = None
    approval_id: str | None = None
    stage_results: list[StageResult] = Field(default_factory=list)
    stage_timings_ms: dict[str, float] = Field(default_factory=dict)

    @property
    def primary_violation(self) -> Violation | None:
        return pick_primary_violation(self.violations)
