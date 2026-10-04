"""Pydantic models mirroring WIKI/api-contract.md exactly.

Control-layer response/request shapes come from the sections "Control layer
- auth and identity" and "Control layer - proxy"; the demo agent's own
request/response shapes come from "Demo agent service". The demo agent never
imports control_layer code, so these models are the sole source of truth for
what is sent and parsed on the wire.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

ToolCallDecision = Literal["approve", "reject"]


class Identity(BaseModel):
    sub: str
    name: str
    role: str
    location: str
    region: str
    agent_id: str


class ProviderInfo(BaseModel):
    name: str
    model: str


class BudgetFull(BaseModel):
    tokens_used: int
    tokens_limit: int
    cost_used_usd: float | None = None
    cost_limit_usd: float | None = None
    resets_at: str | None = None


class RiskInfo(BaseModel):
    score: int | None = None
    level: str | None = None


class ToolDescriptor(BaseModel):
    server: str
    name: str
    qualified_name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    data_region: str | None = None
    scope: str | None = None
    provisioned: bool | None = None


class ProtectionState(BaseModel):
    mode: str = "enforce"
    changed_at: str | None = None


class MeResponse(BaseModel):
    identity: Identity
    tools: list[ToolDescriptor] = Field(default_factory=list)
    policy: dict[str, Any] | None = None
    budget: BudgetFull
    risk: RiskInfo | None = None
    provider: ProviderInfo
    protection: ProtectionState = Field(default_factory=ProtectionState)


class ToolsListResponse(BaseModel):
    tools: list[ToolDescriptor] = Field(default_factory=list)


class ToolCallFunction(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    id: str
    type: str = "function"
    function: ToolCallFunction


class ChatMessage(BaseModel):
    role: str
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    response_format: dict[str, Any] | None = None
    stream: bool = False


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ControlLayerExtension(BaseModel):
    call_id: str
    status: str
    stage: str | None = None
    rule_id: str | None = None
    reason: str | None = None
    items_masked: int | None = None
    proxy_latency_ms: float | None = None
    upstream_latency_ms: float | None = None


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str | None = None


class ChatCompletionResponse(BaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: Usage
    control_layer: ControlLayerExtension


class ToolCallRequest(BaseModel):
    server: str
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    session_id: str


class ToolResultPayload(BaseModel):
    content_text: str
    structured_content: Any | None = None
    is_error: bool = False


class ApprovalInfo(BaseModel):
    id: str
    expires_at: str | None = None


class ToolCallOutcome(BaseModel):
    call_id: str
    status: str
    stage: str | None = None
    rule_id: str | None = None
    reason: str | None = None
    items_masked: int | None = None
    items_restored: int | None = None
    result: ToolResultPayload | None = None
    approval: ApprovalInfo | None = None


class RejectResult(BaseModel):
    id: str
    status: str


class ErrorDetail(BaseModel):
    code: str
    status: str | None = None
    stage: str | None = None
    rule_id: str | None = None
    reason: str | None = None
    owasp: list[str] | None = None
    call_id: str | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class ToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    call_id: str
    tool: str
    arguments: dict[str, Any]
    status: str
    stage: str | None = None
    rule_id: str | None = None
    reason: str | None = None
    items_masked: int = 0
    items_restored: int = 0
    result_preview: str | None = None


class ApprovalRequiredEvent(BaseModel):
    type: Literal["approval_required"] = "approval_required"
    approval_id: str
    tool: str
    arguments: dict[str, Any]
    rule_id: str | None = None
    reason: str | None = None
    call_id: str | None = None


class AssistantTextEvent(BaseModel):
    type: Literal["assistant_text"] = "assistant_text"
    text: str
    status: str | None = None
    stage: str | None = None
    rule_id: str | None = None
    reason: str | None = None
    call_id: str | None = None


class NoticeEvent(BaseModel):
    type: Literal["notice"] = "notice"
    status: str
    stage: str | None = None
    rule_id: str | None = None
    reason: str | None = None
    call_id: str | None = None


Event = Annotated[
    ToolCallEvent | ApprovalRequiredEvent | AssistantTextEvent | NoticeEvent,
    Field(discriminator="type"),
]


class AgentBudget(BaseModel):
    tokens_used: int
    tokens_limit: int


class AgentChatRequest(BaseModel):
    session_id: str
    message: str


class AgentChatResponse(BaseModel):
    session_id: str
    events: list[Event]
    budget: AgentBudget


class AgentApprovalRequest(BaseModel):
    session_id: str
    decision: ToolCallDecision


class AgentHealthResponse(BaseModel):
    status: str
    control_layer: str
    provider: ProviderInfo | None = None
