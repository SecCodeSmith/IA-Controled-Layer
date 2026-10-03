from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from control_layer.domain.models.enums import Severity


class RiskProfile(BaseModel):
    model_config = ConfigDict(frozen=False)

    sub: str
    score: int = 0
    level: Severity = Severity.low
    signals: list[str] = Field(default_factory=list)
