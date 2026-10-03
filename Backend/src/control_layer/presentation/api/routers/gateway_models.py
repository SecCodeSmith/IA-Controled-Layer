from __future__ import annotations

from fastapi import APIRouter

from control_layer.presentation.api.dependencies import ContainerDep, GatewayTokenDep

router = APIRouter(prefix="/v1", tags=["gateway"])


@router.get("/models")
async def list_models(_token: GatewayTokenDep, container: ContainerDep) -> dict:
    models = await container.model_directory.list_models()
    return {
        "object": "list",
        "data": [
            {"id": m.model, "object": "model", "created": 0, "owned_by": m.provider}
            for m in models
        ],
    }
