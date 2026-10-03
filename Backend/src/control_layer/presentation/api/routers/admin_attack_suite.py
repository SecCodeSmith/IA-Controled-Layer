from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Literal

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
from control_layer.selftest.scenarios import SCENARIOS

router = APIRouter(prefix="/api/attack-suite", tags=["admin"], dependencies=AdminDeps)


def _run_fields(run: AttackRun) -> dict:
    return {
        "run_id": run.run_id,
        "number": run.number,
        "agent": run.agent,
        "started_at": run.started_at,
        "scenarios": [
            ScenarioRunState.model_validate(scenario.model_dump(mode="json"))
            for scenario in run.scenarios
        ],
    }


@router.get("/scenarios", response_model=ScenarioListResponse)
async def scenarios() -> ScenarioListResponse:
    return ScenarioListResponse(
        scenarios=[ScenarioSchema.model_validate(s.model_dump()) for s in SCENARIOS]
    )


@router.post("/run", response_model=AttackSuiteRunResponse)
async def start_run(
    container: ContainerDep, agent: Literal["scripted", "ollama"] = "scripted"
) -> AttackSuiteRunResponse:
    run = await container.attack_runs.start(agent)
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
