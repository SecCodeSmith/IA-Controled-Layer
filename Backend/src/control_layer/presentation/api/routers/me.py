from __future__ import annotations

from fastapi import APIRouter

from control_layer.presentation.api.dependencies import BearerDep, ContainerDep, SessionDep
from control_layer.presentation.api.schemas.me import (
    BudgetSummary,
    MeProtection,
    MeResponse,
    PolicyRef,
    RiskSummary,
)

router = APIRouter(prefix="/v1", tags=["me"])


@router.get("/me", response_model=MeResponse)
async def me(token: BearerDep, session: SessionDep, container: ContainerDep) -> MeResponse:
    identity = await container.identity_service.resolve(token, session or "")
    view = await container.get_me.execute(identity)
    return MeResponse(
        identity=identity.model_copy(update={"session_id": session}),
        tools=view.tools,
        policy=PolicyRef(name=view.policy_name, version=view.policy_version),
        budget=BudgetSummary.model_validate(view.budget.model_dump()),
        risk=RiskSummary(score=view.risk.score, level=view.risk.level.value),
        provider=view.provider,
        protection=MeProtection(
            mode=view.protection.mode, changed_at=view.protection.changed_at
        ),
    )
