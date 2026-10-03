from __future__ import annotations

from fastapi import APIRouter

from control_layer.presentation.api.dependencies import ContainerDep
from control_layer.presentation.api.schemas.health import HealthResponse
from control_layer.presentation.composition_root import collect_health

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(container: ContainerDep) -> HealthResponse:
    view = await collect_health(container)
    return HealthResponse.model_validate(view.model_dump())
