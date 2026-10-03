from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response

from control_layer.presentation.api.dependencies import AdminDeps, ContainerDep
from control_layer.presentation.api.mappers import alert_schema
from control_layer.presentation.api.schemas.alerts import AlertListResponse

router = APIRouter(prefix="/api/alerts", tags=["admin"], dependencies=AdminDeps)


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    container: ContainerDep,
    limit: int = 100,
    user: str | None = None,
    rule_id: str | None = None,
) -> AlertListResponse:
    alerts = await container.list_alerts.execute(limit=limit, user=user, rule_id=rule_id)
    return AlertListResponse(items=[alert_schema(a) for a in alerts])


@router.get("/export")
async def export_alerts(container: ContainerDep) -> Response:
    export = await container.export_alerts.execute()
    return Response(
        content=export.content,
        media_type=export.media_type,
        headers={"Content-Disposition": f'attachment; filename="{export.filename}"'},
    )
