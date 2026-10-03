from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from control_layer.domain.models.enums import InterceptionPoint, RuleAction, Severity, StageName


class Rule(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    type: str
    stage: StageName
    on: list[InterceptionPoint] = Field(default_factory=InterceptionPoint.all)
    match: dict | None = None
    detect: list[str] | None = None
    action: RuleAction = RuleAction.flag
    params: dict = Field(default_factory=dict)
    owasp: list[str] = Field(default_factory=list)
    severity: Severity = Severity.medium
    enabled: bool = True
