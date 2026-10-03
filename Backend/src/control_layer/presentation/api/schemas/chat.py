from __future__ import annotations

from pydantic import BaseModel

from control_layer.domain.models.chat import ChatCompletionChoice
from control_layer.domain.models.enums import CallStatus, StageName


class ControlLayerExtension(BaseModel):
    call_id: str
    status: CallStatus
    stage: StageName | None = None
    rule_id: str | None = None
    reason: str | None = None
    items_masked: int = 0
    proxy_latency_ms: float
    upstream_latency_ms: float


class ChatUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponseEnvelope(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: ChatUsage
    control_layer: ControlLayerExtension
