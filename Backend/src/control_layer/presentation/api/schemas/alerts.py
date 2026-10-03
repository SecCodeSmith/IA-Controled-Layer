from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from control_layer.domain.models.enums import CallStatus, Severity, StageName
from control_layer.presentation.api.schemas.feed import FeedUserRef


class AlertSchema(BaseModel):
    id: str
    created_at: datetime
    call_id: str
    user: FeedUserRef
    status: CallStatus
    stage: StageName
    rule_id: str | None = None
    severity: Severity
    owasp: list[str] = []
    reason: str
    evidence: list[str] = []


class AlertListResponse(BaseModel):
    items: list[AlertSchema]
