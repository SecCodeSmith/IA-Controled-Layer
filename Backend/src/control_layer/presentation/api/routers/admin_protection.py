from __future__ import annotations

from fastapi import APIRouter

from control_layer.domain.models.enums import ProtectionMode
from control_layer.presentation.api.dependencies import AdminDeps, ContainerDep
from control_layer.presentation.api.schemas.protection import (
    ProtectionModeRequest,
    ProtectionResponse,
)
from control_layer.presentation.composition_root import Container

router = APIRouter(prefix="/api/protection", tags=["admin"], dependencies=AdminDeps)


async def _view(container: Container) -> ProtectionResponse:
    view = await container.manage_protection.get()
    changed_at, changed_by = await container.protection.get_changed()
    return ProtectionResponse.model_validate(
        {**view.model_dump(), "changed_at": changed_at, "changed_by": changed_by}
    )


@router.get("", response_model=ProtectionResponse)
async def get_protection(container: ContainerDep) -> ProtectionResponse:
    return await _view(container)


@router.put("", response_model=ProtectionResponse)
async def set_protection(
    body: ProtectionModeRequest, container: ContainerDep
) -> ProtectionResponse:
    previous = await container.protection.get_mode()
    await container.manage_protection.set_mode(body.mode)
    await container.admin_actions.record(
        "admin.protection",
        details={
            "reason": f"protection mode set to {body.mode.value} (was {previous.value})",
            "from": previous.value,
            "to": body.mode.value,
        },
        loosening=body.mode != ProtectionMode.enforce,
    )
    return await _view(container)


@router.delete("/overrides", response_model=ProtectionResponse)
async def clear_overrides(container: ContainerDep) -> ProtectionResponse:
    previous = await container.protection.get_rule_overrides()
    await container.manage_protection.clear_overrides()
    await container.admin_actions.record(
        "admin.rule_override",
        details={
            "reason": "rule overrides cleared",
            "cleared": sorted(previous),
        },
        loosening=False,
    )
    return await _view(container)
