from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from control_layer.presentation.api.dependencies import BearerDep, ContainerDep
from control_layer.presentation.api.mappers import approval_detail, tool_outcome_response
from control_layer.presentation.api.schemas.approvals import (
    ApprovalDetailResponse,
    ApprovalRejectResponse,
)

router = APIRouter(prefix="/v1/approvals", tags=["approvals"])


@router.get("/{approval_id}", response_model=ApprovalDetailResponse)
async def get_approval(
    approval_id: str, token: BearerDep, container: ContainerDep
) -> ApprovalDetailResponse:
    return approval_detail(await container.get_approval.execute(token, approval_id))


@router.post("/{approval_id}/approve")
async def approve(approval_id: str, token: BearerDep, container: ContainerDep) -> JSONResponse:
    outcome = await container.execute_approval.approve(token, approval_id)
    return tool_outcome_response(outcome)


@router.post("/{approval_id}/reject", response_model=ApprovalRejectResponse)
async def reject(
    approval_id: str, token: BearerDep, container: ContainerDep
) -> ApprovalRejectResponse:
    approval = await container.execute_approval.reject(token, approval_id)
    return ApprovalRejectResponse(id=approval.id, status=approval.status)
