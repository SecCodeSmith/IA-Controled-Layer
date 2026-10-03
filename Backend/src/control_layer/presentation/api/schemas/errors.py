from __future__ import annotations

from pydantic import BaseModel

from control_layer.domain.models.enums import CallStatus, StageName


class ErrorDetail(BaseModel):
    code: str
    status: CallStatus
    stage: StageName | None = None
    rule_id: str | None = None
    reason: str
    owasp: list[str] = []
    call_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
