from __future__ import annotations

from fastapi import APIRouter

from control_layer.application.use_cases.admin.workbench_views import TraceInput
from control_layer.presentation.api.dependencies import AdminDeps, ContainerDep
from control_layer.presentation.api.schemas.workbench import (
    ResourceMatrixResponse,
    TraceRequest,
    TraceResponse,
)

router = APIRouter(prefix="/api/workbench", tags=["admin"], dependencies=AdminDeps)

_ENDPOINTS = ["POST /api/workbench/trace", "GET /api/workbench/resources"]


@router.get("")
async def workbench_info() -> dict[str, str | list[str]]:
    return {"status": "ok", "endpoints": _ENDPOINTS}


@router.post("/trace", response_model=TraceResponse)
async def trace(request: TraceRequest, container: ContainerDep) -> TraceResponse:
    view = await container.workbench.trace.execute(TraceInput.model_validate(request.model_dump()))
    return TraceResponse.model_validate(view.model_dump())


@router.get("/resources", response_model=ResourceMatrixResponse)
async def resources(container: ContainerDep) -> ResourceMatrixResponse:
    view = await container.workbench.matrix.execute()
    return ResourceMatrixResponse.model_validate(view.model_dump())
