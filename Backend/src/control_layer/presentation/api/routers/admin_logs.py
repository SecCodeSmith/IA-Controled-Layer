from __future__ import annotations

from fastapi import APIRouter

from control_layer.presentation.api.dependencies import AdminDeps, ContainerDep
from control_layer.presentation.api.schemas.logs import ClearLogsResponse

router = APIRouter(prefix="/api/logs", tags=["admin"], dependencies=AdminDeps)


@router.post("/clear", response_model=ClearLogsResponse)
async def clear_logs(container: ContainerDep) -> ClearLogsResponse:
    cleared = await container.clear_logs.execute()
    await container.admin_actions.record(
        "admin.logs", details={"reason": "logs cleared", "cleared": cleared}, loosening=True
    )
    return ClearLogsResponse(cleared=cleared)
