from __future__ import annotations

from fastapi import APIRouter

from control_layer.presentation.api.dependencies import AdminDeps, ContainerDep
from control_layer.presentation.api.schemas.reports import SecurityReportResponse

router = APIRouter(prefix="/api/reports", tags=["admin"], dependencies=AdminDeps)


@router.get("/security", response_model=SecurityReportResponse)
async def security_report(container: ContainerDep, period: str = "24h") -> SecurityReportResponse:
    report = await container.security_report.execute(period)
    return SecurityReportResponse.model_validate(report.model_dump())
