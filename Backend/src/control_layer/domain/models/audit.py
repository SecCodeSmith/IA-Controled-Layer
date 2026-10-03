from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from control_layer.domain.models.enums import CallKind, CallStatus, StageName
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.provider import ProviderInfo


class CallDecisionInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: CallStatus
    stage: StageName | None = None
    rule_id: str | None = None
    reason: str | None = None
    owasp: list[str] = Field(default_factory=list)


class CallRequestInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    summary: str
    payload: dict = Field(default_factory=dict)


class CallResponseInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    raw: str | None = None
    delivered: str | None = None


class TokensInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    prompt: int = 0
    completion: int = 0
    total: int = 0


class CallLatency(BaseModel):
    model_config = ConfigDict(frozen=True)

    proxy_ms: float
    upstream_ms: float
    stages: dict[str, float] = Field(default_factory=dict)

    @computed_field
    @property
    def overhead_ms(self) -> float:
        return max(self.proxy_ms - self.upstream_ms, 0.0)


class CallRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    call_id: str
    timestamp: datetime
    identity: Identity
    kind: CallKind
    target: str
    mcp_server: str | None = None
    decision: CallDecisionInfo
    matched_rule_yaml: str | None = None
    request: CallRequestInfo
    response: CallResponseInfo
    items_masked: int = 0
    tokens: TokensInfo
    cost_usd: float = 0.0
    latency: CallLatency
    provider: ProviderInfo
