from __future__ import annotations

from fastapi import APIRouter

from control_layer.presentation.api.dependencies import AdminDeps, ContainerDep
from control_layer.presentation.api.schemas.policy import PolicyViewResponse

router = APIRouter(prefix="/api/policy", tags=["admin"], dependencies=AdminDeps)


@router.get("", response_model=PolicyViewResponse)
async def view_policy(container: ContainerDep) -> PolicyViewResponse:
    view = await container.policy_view.execute()
    return PolicyViewResponse.model_validate(view.model_dump())


@router.post("/reload", response_model=PolicyViewResponse)
async def reload_policy(container: ContainerDep) -> PolicyViewResponse:
    view = await container.reload_policy.execute()
    return PolicyViewResponse.model_validate(view.model_dump())
