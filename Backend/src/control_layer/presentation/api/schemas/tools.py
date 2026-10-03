from __future__ import annotations

from pydantic import BaseModel

from control_layer.domain.models.enums import CallStatus, StageName
from control_layer.domain.models.tool import ToolCallResult, ToolDescriptor


class ToolsListResponse(BaseModel):
    tools: list[ToolDescriptor]


class ToolCallRequestBody(BaseModel):
    server: str
    tool: str
    arguments: dict = {}
    session_id: str | None = None


class ToolCallResponse(BaseModel):
    call_id: str
    status: CallStatus
    stage: StageName | None = None
    rule_id: str | None = None
    reason: str | None = None
    items_masked: int = 0
    result: ToolCallResult


class PendingApprovalRef(BaseModel):
    id: str
    expires_at: str | None = None


class ToolCallEscalatedResponse(BaseModel):
    call_id: str
    status: CallStatus
    stage: StageName | None = None
    rule_id: str | None = None
    reason: str | None = None
    approval: PendingApprovalRef
