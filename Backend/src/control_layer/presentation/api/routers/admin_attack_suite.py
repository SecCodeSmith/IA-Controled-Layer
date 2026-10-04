from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Literal

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from control_layer.application.selftest.attack_run import AttackRun
from control_layer.presentation.api.dependencies import AdminDeps, ContainerDep
from control_layer.presentation.api.schemas.attack_suite import (
    AttackSuiteRunDetailResponse,
    AttackSuiteRunResponse,
    RunSummary,
    ScenarioListResponse,
    ScenarioRunState,
    ScenarioSchema,
)
from control_layer.selftest.scenarios import SCENARIOS, Scenario

router = APIRouter(prefix="/api/attack-suite", tags=["admin"], dependencies=AdminDeps)


def _run_fields(run: AttackRun) -> dict:
    return {
        "run_id": run.run_id,
        "number": run.number,
        "agent": run.agent,
        "provider": run.provider,
        "model": run.model,
        "protection_mode": run.protection_mode,
        "started_at": run.started_at,
        "scenarios": [
            ScenarioRunState.model_validate(scenario.model_dump(mode="json"))
            for scenario in run.scenarios
        ],
    }


_MESSAGE_LIMIT = 200


def _public_step(step: dict[str, Any]) -> dict[str, Any]:
    rendered = dict(step)
    if isinstance(rendered.get("message"), str):
        rendered["message"] = rendered["message"][:_MESSAGE_LIMIT]
    if isinstance(rendered.get("step"), dict):
        rendered["step"] = _public_step(rendered["step"])
    return rendered


def _scenario_schema(scenario: Scenario) -> ScenarioSchema:
    return ScenarioSchema.model_validate(
        {
            **scenario.model_dump(exclude={"steps"}),
            "description": getattr(scenario, "description", ""),
            "steps": [_public_step(step) for step in scenario.steps],
        }
    )


@router.get("/scenarios", response_model=ScenarioListResponse)
async def scenarios() -> ScenarioListResponse:
    return ScenarioListResponse(scenarios=[_scenario_schema(s) for s in SCENARIOS])


@router.post("/run", response_model=AttackSuiteRunResponse)
async def start_run(
    container: ContainerDep, agent: Literal["scripted", "ollama"] = "scripted"
) -> AttackSuiteRunResponse:
    provider = container.model_provider.describe()
    run = await container.attack_runs.start(
        agent,
        provider=provider.name,
        model=provider.model,
        protection_mode=str(await container.protection.get_mode()),
    )
    return AttackSuiteRunResponse(**_run_fields(run))


@router.get("/runs/{run_id}", response_model=AttackSuiteRunDetailResponse)
async def get_run(run_id: str, container: ContainerDep) -> AttackSuiteRunDetailResponse:
    run = container.attack_runs.get(run_id)
    summary = RunSummary.model_validate(run.summary.model_dump())
    return AttackSuiteRunDetailResponse(**_run_fields(run), summary=summary)


@router.get("/runs/{run_id}/stream")
async def run_stream(run_id: str, container: ContainerDep) -> EventSourceResponse:
    subscription = container.attack_runs.subscribe(run_id)

    async def events() -> AsyncIterator[dict[str, str]]:
        async for event in subscription:
            yield {"event": event.event, "data": json.dumps(event.data, default=str)}
            if event.event == "run_complete":
                return

    return EventSourceResponse(events())
