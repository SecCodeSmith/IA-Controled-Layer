from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from control_layer.application.selftest.scenario_client import StepObservation
from control_layer.application.selftest.scenario_executor import ScenarioStatus
from control_layer.domain.models.enums import StageName
from control_layer.selftest.scenarios import Scenario, ScenarioExpectation

_SUMMARY_FIELD_BY_STATUS: dict[ScenarioStatus, str] = {
    ScenarioStatus.STOPPED: "stopped",
    ScenarioStatus.PASSED: "passed",
    ScenarioStatus.SUCCEEDED: "succeeded",
    ScenarioStatus.NOT_ATTEMPTED: "not_attempted",
    ScenarioStatus.RUNNING: "running",
    ScenarioStatus.PENDING: "pending",
    ScenarioStatus.ERROR: "error",
}


class AttackRunScenario(BaseModel):
    model_config = ConfigDict(frozen=False)

    id: str
    name: str
    kind: str
    actor: str
    stage: StageName
    expected: ScenarioExpectation
    owasp: list[str] = Field(default_factory=list)
    status: ScenarioStatus = ScenarioStatus.PENDING
    observed: StepObservation | None = None
    duration_ms: float | None = None
    via: Literal["agent", "scripted"] = "scripted"
    agent_driven: bool = True
    description: str = ""
    trace: list[StepObservation] = Field(default_factory=list)
    explanation: str | None = None
    error: str | None = None

    @classmethod
    def from_scenario(cls, scenario: Scenario) -> AttackRunScenario:
        return cls(
            id=scenario.id,
            name=scenario.name,
            kind=scenario.kind,
            actor=scenario.actor,
            stage=scenario.stage,
            expected=scenario.expected,
            owasp=list(scenario.owasp),
            agent_driven=scenario.agent_driven,
            description=getattr(scenario, "description", ""),
        )


class AttackRunSummary(BaseModel):
    model_config = ConfigDict(frozen=False)

    stopped: int = 0
    passed: int = 0
    succeeded: int = 0
    not_attempted: int = 0
    running: int = 0
    pending: int = 0
    error: int = 0

    @classmethod
    def from_scenarios(cls, scenarios: list[AttackRunScenario]) -> AttackRunSummary:
        counts = dict.fromkeys(_SUMMARY_FIELD_BY_STATUS.values(), 0)
        for scenario in scenarios:
            field = _SUMMARY_FIELD_BY_STATUS[scenario.status]
            counts[field] += 1
        return cls(**counts)


class AttackRun(BaseModel):
    model_config = ConfigDict(frozen=False)

    run_id: str
    number: int
    agent: str
    provider: str = ""
    model: str = ""
    protection_mode: str = "enforce"
    started_at: datetime
    finished_at: datetime | None = None
    scenarios: list[AttackRunScenario]
    summary: AttackRunSummary = Field(default_factory=AttackRunSummary)
