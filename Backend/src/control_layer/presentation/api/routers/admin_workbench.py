from __future__ import annotations

from fastapi import APIRouter

from control_layer.presentation.api.dependencies import AdminDeps

router = APIRouter(prefix="/api/workbench", tags=["admin"], dependencies=AdminDeps)


@router.get("", status_code=501)
async def get_workbench() -> dict[str, str]:
    return {"status": "not_implemented"}
