from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from control_layer.domain.models.enums import ApprovalStatus
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.tool import ToolCallRequest


class PendingApproval(BaseModel):
    model_config = ConfigDict(frozen=False)

    id: str
    identity: Identity
    tool_call: ToolCallRequest
    created_at: datetime
    rule_id: str
    status: ApprovalStatus
    expires_at: datetime | None = None
    reason: str | None = None
