from __future__ import annotations

from fastapi import APIRouter

from control_layer.presentation.api.dependencies import AdminDeps, ContainerDep
from control_layer.presentation.api.schemas.stats import StatsResponse

router = APIRouter(prefix="/api/stats", tags=["admin"], dependencies=AdminDeps)


@router.get("", response_model=StatsResponse)
async def stats(container: ContainerDep) -> StatsResponse:
    view = await container.stats.compute()
    return StatsResponse.model_validate(view.model_dump())
