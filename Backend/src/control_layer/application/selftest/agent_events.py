from __future__ import annotations

from control_layer.application.selftest.scenario_client import StepObservation
from control_layer.domain.models.enums import CallStatus, StageName

LLM_TARGET = "llm.complete"


def _stage(value: str | None) -> StageName | None:
    return StageName(value) if value else None


def _approval_observation(event: dict) -> StepObservation:
    return StepObservation(
        http_status=202,
        status=CallStatus.ESCALATED,
        stage=StageName.authorization,
        rule_id=event.get("rule_id"),
        reason=event.get("reason"),
        approval_id=event.get("approval_id"),
        target=event.get("tool"),
        call_id=event.get("call_id"),
    )


def _decision_observation(event: dict, target: str | None) -> StepObservation:
    return StepObservation(
        http_status=200,
        status=CallStatus(event["status"]),
        stage=_stage(event.get("stage")),
        rule_id=event.get("rule_id"),
        reason=event.get("reason"),
        target=target,
        call_id=event.get("call_id"),
    )


def observations_from_events(events: list[dict]) -> list[StepObservation]:
    observations: list[StepObservation] = []
    for event in events:
        kind = event.get("type")
        if kind == "approval_required":
            observations.append(_approval_observation(event))
        elif kind == "tool_call" and event.get("status"):
            observations.append(_decision_observation(event, event.get("tool")))
        elif kind in ("assistant_text", "notice") and event.get("status"):
            observations.append(_decision_observation(event, LLM_TARGET))
    return observations
