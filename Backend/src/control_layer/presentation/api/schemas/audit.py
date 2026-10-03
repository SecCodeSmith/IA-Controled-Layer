from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from control_layer.domain.models.audit import (
    CallLatency,
    CallRequestInfo,
    CallResponseInfo,
    TokensInfo,
)
from control_layer.domain.models.enums import CallKind, CallStatus, StageName
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.provider import ProviderInfo
from control_layer.presentation.api.schemas.feed import FeedUserRef


class AuditRow(BaseModel):
    call_id: str
    time: datetime
    user: FeedUserRef
    kind: CallKind
    target: str
    status: CallStatus
    stage: StageName | None = None
    rule_id: str | None = None
    reason: str | None = None
    tokens: int = 0
    cost_usd: float = 0.0
    proxy_latency_ms: float = 0.0


class AuditListResponse(BaseModel):
    items: list[AuditRow]


class AuditDecisionInfo(BaseModel):
    status: CallStatus
    stage: StageName | None = None
    rule_id: str | None = None
    reason: str | None = None
    owasp: list[str] = []


class AuditDetailResponse(BaseModel):
    call_id: str
    timestamp: datetime
    identity: Identity
    kind: CallKind
    target: str
    mcp_server: str | None = None
    decision: AuditDecisionInfo
    matched_rule_yaml: str | None = None
    request: CallRequestInfo
    response: CallResponseInfo
    items_masked: int = 0
    tokens: TokensInfo
    cost_usd: float = 0.0
    latency: CallLatency
    provider: ProviderInfo


class AuditExportQuery(BaseModel):
    format: Literal["jsonl", "csv", "xlsx"] = "jsonl"
