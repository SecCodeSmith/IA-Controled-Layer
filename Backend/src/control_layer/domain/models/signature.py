from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from control_layer.domain.models.enums import InterceptionPoint, Severity


class Signature(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    pattern: str
    categories: list[str] = Field(default_factory=list)
    severity: Severity = Severity.medium
    reference: str | None = None
    owasp: list[str] = Field(default_factory=list)
    points: list[InterceptionPoint] = Field(default_factory=list)
