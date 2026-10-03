from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

from control_layer.domain.models.enums import CallStatus, StageName


class ScenarioRunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    PASSED = "PASSED"
    SUCCEEDED = "SUCCEEDED"
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    ERROR = "ERROR"


class ScenarioExpectation(BaseModel):
    status: CallStatus
    rule_id: str | None = None


class ScenarioSchema(BaseModel):
    id: str
    name: str
    kind: Literal["positive", "negative"]
    actor: str
    stage: StageName
    expected: ScenarioExpectation
    owasp: list[str] = []
    agent_driven: bool = True


class ScenarioListResponse(BaseModel):
    scenarios: list[ScenarioSchema]


class ObservedOutcome(BaseModel):
    status: CallStatus
    stage: StageName | None = None
    rule_id: str | None = None


class ScenarioRunState(ScenarioSchema):
    status: ScenarioRunStatus = ScenarioRunStatus.PENDING
    observed: ObservedOutcome | None = None
    duration_ms: float | None = None
    via: Literal["agent", "scripted"] = "scripted"


class RunSummary(BaseModel):
    stopped: int = 0
    passed: int = 0
    succeeded: int = 0
    not_attempted: int = 0
    running: int = 0
    pending: int = 0
    error: int = 0


class AttackSuiteRunResponse(BaseModel):
    run_id: str
    number: int
    agent: Literal["scripted", "ollama"]
    provider: str = ""
    model: str = ""
    protection_mode: str = "enforce"
    started_at: datetime
    scenarios: list[ScenarioRunState]


class AttackSuiteRunDetailResponse(AttackSuiteRunResponse):
    summary: RunSummary


class ScenarioEvent(BaseModel):
    id: str
    status: ScenarioRunStatus
    observed: ObservedOutcome | None = None
    duration_ms: float | None = None
    via: Literal["agent", "scripted"] = "scripted"


class RunCompleteEvent(BaseModel):
    summary: RunSummary
