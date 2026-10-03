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
    return await container.model_selection.select(body.provider, body.model)
