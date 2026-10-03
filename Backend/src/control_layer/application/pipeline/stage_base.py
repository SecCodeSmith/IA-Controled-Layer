from __future__ import annotations

from abc import ABC

from control_layer.domain.models.decision import StageResult, Violation
from control_layer.domain.models.enums import RuleAction, StageName


class BaseStage(ABC):
    name: StageName

    def __init__(self, name: StageName) -> None:
        self.name = name

    def allow(self, timing_ms: float, *, cache_hit: bool = False) -> StageResult:
        return self.result(RuleAction.allow, timing_ms, cache_hit=cache_hit)

    def result(
        self,
        action: RuleAction,
        timing_ms: float,
        *,
        violations: list[Violation] | None = None,
        masked_text: str | None = None,
        approval_id: str | None = None,
        cache_hit: bool = False,
        reason: str | None = None,
    ) -> StageResult:
        return StageResult(
            stage=self.name,
            action=action,
            violations=violations or [],
            masked_text=masked_text,
            approval_id=approval_id,
            timing_ms=timing_ms,
            cache_hit=cache_hit,
            reason=reason,
        )
