from __future__ import annotations

from typing import Literal

from fastapi import APIRouter

from control_layer.presentation.api.dependencies import AdminDeps, ContainerDep
from control_layer.presentation.api.schemas.demo import DemoResetResponse

router = APIRouter(prefix="/api/demo", tags=["admin"], dependencies=AdminDeps)


@router.post("/reset", response_model=DemoResetResponse)
async def reset(
    container: ContainerDep, scope: Literal["all", "behavior"] = "all"
) -> DemoResetResponse:
    if scope == "behavior":
        await container.reset_runtime_state()
    else:
        await container.reset_demo.execute()
    return DemoResetResponse()
