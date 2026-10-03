from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from control_layer.domain.models.approval import PendingApproval
from control_layer.domain.models.budget_usage import BudgetUsage
from control_layer.domain.models.chat import ChatCompletionResponse
from control_layer.domain.models.enums import CallStatus, StageName
from control_layer.domain.models.identity import Identity, TokenClaims
from control_layer.domain.models.provider import ProviderInfo
from control_layer.domain.models.risk import RiskProfile
from control_layer.domain.models.tool import ToolCallResult, ToolDescriptor


class ChatCompletionOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    call_id: str
    response: ChatCompletionResponse
    status: CallStatus
    stage: StageName | None = None
    rule_id: str | None = None
    reason: str | None = None
    items_masked: int = 0
    proxy_latency_ms: float
    upstream_latency_ms: float


class ToolCallOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    call_id: str
    status: CallStatus
    stage: StageName | None = None
    rule_id: str | None = None
    reason: str | None = None
    items_masked: int = 0
    result: ToolCallResult | None = None
    approval: PendingApproval | None = None


class MeView(BaseModel):
    model_config = ConfigDict(frozen=True)

    identity: Identity
    tools: list[ToolDescriptor]
    policy_name: str
    policy_version: int
    budget: BudgetUsage
    risk: RiskProfile
    provider: ProviderInfo


class TokenIssued(BaseModel):
    model_config = ConfigDict(frozen=True)

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    claims: TokenClaims
