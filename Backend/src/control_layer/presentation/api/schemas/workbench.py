from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from control_layer.domain.models.classifier import ClassifierTrace
from control_layer.domain.models.enums import CallStatus, RuleAction, StageName
from control_layer.domain.models.resource import ResourceGrant

TraceKind = Literal["prompt", "tool_call"]
JudgeVerdict = Literal["allow", "flag", "block"]


class ToolCallSpec(BaseModel):
    server: str
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class TraceRequest(BaseModel):
    actor: str
    kind: TraceKind
    text: str | None = None
    tool_call: ToolCallSpec | None = None
    force_verify: bool = False

    @model_validator(mode="after")
    def _payload_matches_kind(self) -> TraceRequest:
        if self.kind == "prompt" and not self.text:
            raise ValueError("a prompt trace requires 'text'")
        if self.kind == "tool_call" and self.tool_call is None:
            raise ValueError("a tool_call trace requires 'tool_call'")
        return self


class ViolationView(BaseModel):
    rule_id: str
    action: RuleAction
    confidence: float = 1.0
    reason: str | None = None
    evidence: list[str] = Field(default_factory=list)


class StageView(BaseModel):
    stage: StageName
    action: RuleAction
    timing_ms: float
    cache_hit: bool = False
    violations: list[ViolationView] = Field(default_factory=list)


class JudgeView(BaseModel):
    verdict: JudgeVerdict
    confidence: float
    reason: str | None = None


class TraceResponse(BaseModel):
    call_id: str
    kind: TraceKind
    status: CallStatus
    action: RuleAction
    stage: StageName | None = None
    rule_id: str | None = None
    reason: str | None = None
    masked_text: str | None = None
    stages: list[StageView] = Field(default_factory=list)
    classifier_trace: ClassifierTrace | None = None
    judge: JudgeView | None = None
    training_sample_id: str | None = None
    raw_result: Any | None = None
    delivered_result: Any | None = None


class ResourceView(BaseModel):
    id: str
    server: str
    tools: list[str] = Field(default_factory=list)
    path_argument: str | None = None
    records: str | None = None
    grants: dict[str, ResourceGrant] = Field(default_factory=dict)


class ResourceMatrixResponse(BaseModel):
    roles: list[str]
    resources: list[ResourceView] = Field(default_factory=list)
