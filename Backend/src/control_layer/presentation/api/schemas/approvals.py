from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from control_layer.domain.models.enums import ApprovalStatus


class ApprovalDetailResponse(BaseModel):
    id: str
    status: ApprovalStatus
    tool: str
    arguments: dict = {}
    rule_id: str
    reason: str | None = None
    created_at: datetime
    expires_at: datetime | None = None


class ApprovalRejectResponse(BaseModel):
    id: str
    status: ApprovalStatus
