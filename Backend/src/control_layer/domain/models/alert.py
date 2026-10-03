from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from control_layer.domain.models.enums import CallStatus, Role, Severity, StageName


class AlertUserRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    sub: str
    name: str
    role: Role


class Alert(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    created_at: datetime
    call_id: str
    user: AlertUserRef
    status: CallStatus
    stage: StageName
    rule_id: str | None = None
    severity: Severity
    owasp: list[str] = Field(default_factory=list)
    reason: str
    evidence: list[str] = Field(default_factory=list)
