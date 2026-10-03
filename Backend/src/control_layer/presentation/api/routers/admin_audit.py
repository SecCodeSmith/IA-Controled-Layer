from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from fastapi.responses import Response

from control_layer.application.use_cases.admin.feed import FeedQuery
from control_layer.presentation.api.dependencies import AdminDeps, ContainerDep
from control_layer.presentation.api.mappers import audit_row
from control_layer.presentation.api.schemas.audit import AuditDetailResponse, AuditListResponse

router = APIRouter(prefix="/api/audit", tags=["admin"], dependencies=AdminDeps)


@router.get("", response_model=AuditListResponse)
async def list_audit(
    container: ContainerDep,
    limit: int = 100,
    user: str | None = None,
    status: str | None = None,
    kind: str | None = None,
) -> AuditListResponse:
    records = await container.list_audit.execute(
        FeedQuery(user=user, status=status, kind=kind, limit=limit)
    )
    return AuditListResponse(items=[audit_row(r) for r in records])


@router.get("/export")
async def export_audit(
    container: ContainerDep, format: Literal["jsonl", "csv", "xlsx"] = "jsonl"
) -> Response:
    export = await container.export_audit.execute(format)
    return Response(
        content=export.content,
        media_type=export.media_type,
        headers={"Content-Disposition": f'attachment; filename="{export.filename}"'},
    )


@router.get("/{call_id}", response_model=AuditDetailResponse)
async def call_detail(call_id: str, container: ContainerDep) -> AuditDetailResponse:
    record = await container.call_detail.execute(call_id)
    return AuditDetailResponse.model_validate(record.model_dump())
