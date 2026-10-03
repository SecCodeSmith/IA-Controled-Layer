from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from control_layer.presentation.api.dependencies import AdminDeps, ContainerDep
from control_layer.presentation.api.schemas.metrics import MetricsResponse

router = APIRouter(tags=["admin"], dependencies=AdminDeps)


@router.get("/api/metrics", response_model=MetricsResponse)
async def metrics(container: ContainerDep) -> MetricsResponse:
    return MetricsResponse.model_validate(container.metrics_collector.snapshot().model_dump())


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus(container: ContainerDep) -> PlainTextResponse:
    return PlainTextResponse(
        container.metrics_collector.prometheus_text(),
        media_type="text/plain; version=0.0.4",
    )
