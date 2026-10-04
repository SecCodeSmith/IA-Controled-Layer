from __future__ import annotations

from fastapi import APIRouter

from control_layer.presentation.api.dependencies import AdminDeps

router = APIRouter(prefix="/api/classifier", tags=["admin"], dependencies=AdminDeps)


@router.get("", status_code=501)
async def get_classifier_status() -> dict[str, str]:
    return {"status": "not_implemented"}
