from __future__ import annotations

from fastapi import APIRouter

from control_layer.domain.models.provider import ProviderInfo
from control_layer.presentation.api.dependencies import AdminDeps, ContainerDep
from control_layer.presentation.api.schemas.models import ModelSelectRequest, ModelsResponse

router = APIRouter(prefix="/api/models", tags=["admin"], dependencies=AdminDeps)


@router.get("", response_model=ModelsResponse)
async def list_models(container: ContainerDep) -> ModelsResponse:
    listing = await container.model_selection.list_models()
    return ModelsResponse.model_validate(listing.model_dump())


@router.put("", response_model=ProviderInfo)
async def select_model(body: ModelSelectRequest, container: ContainerDep) -> ProviderInfo:
    previous = container.model_provider.describe()
    active = await container.model_selection.select(body.provider, body.model)
    listing = await container.model_selection.list_models()
    allowed = any(
        entry.provider == body.provider and entry.model == body.model and entry.allowed
        for entry in listing.available
    )
    suffix = "" if allowed else " (not allowlisted)"
    await container.admin_actions.record(
        "admin.model",
        details={
            "reason": f"model switched to {body.model}{suffix}",
            "from": f"{previous.name}/{previous.model}",
            "to": f"{body.provider}/{body.model}",
            "allowlisted": allowed,
        },
        loosening=not allowed,
    )
    return active
