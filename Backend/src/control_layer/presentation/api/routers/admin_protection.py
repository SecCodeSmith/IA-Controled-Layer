from __future__ import annotations

from fastapi import APIRouter

from control_layer.presentation.api.dependencies import AdminDeps, ContainerDep
from control_layer.presentation.api.schemas.protection import (
    ProtectionModeRequest,
    ProtectionResponse,
)

router = APIRouter(prefix="/api/protection", tags=["admin"], dependencies=AdminDeps)


@router.get("", response_model=ProtectionResponse)
async def get_protection(container: ContainerDep) -> ProtectionResponse:
    return ProtectionResponse.model_validate((await container.manage_protection.get()).model_dump())


@router.put("", response_model=ProtectionResponse)
async def set_protection(
    body: ProtectionModeRequest, container: ContainerDep
) -> ProtectionResponse:
    view = await container.manage_protection.set_mode(body.mode)
    return ProtectionResponse.model_validate(view.model_dump())


@router.delete("/overrides", response_model=ProtectionResponse)
async def clear_overrides(container: ContainerDep) -> ProtectionResponse:
    view = await container.manage_protection.clear_overrides()
    return ProtectionResponse.model_validate(view.model_dump())
