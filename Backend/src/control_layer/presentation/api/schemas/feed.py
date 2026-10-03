from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from control_layer.domain.models.enums import CallKind, CallStatus, Role, StageName


class FeedUserRef(BaseModel):
    sub: str
    name: str
    role: Role


class FeedRow(BaseModel):
    call_id: str
    time: datetime
    user: FeedUserRef
    kind: CallKind
    target: str
    status: CallStatus
    stage: StageName | None = None
    rule_id: str | None = None
    reason: str | None = None
    proxy_latency_ms: float = 0.0
    upstream_latency_ms: float = 0.0
    overhead_ms: float = 0.0


class FeedListResponse(BaseModel):
    items: list[FeedRow]
