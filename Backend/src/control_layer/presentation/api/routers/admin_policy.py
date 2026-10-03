from __future__ import annotations

from fastapi import APIRouter
from pydantic import ValidationError

from control_layer.application.use_cases.admin.policy_view import PolicyView
from control_layer.domain.models.enums import StageName
from control_layer.presentation.api.dependencies import AdminDeps, ContainerDep
from control_layer.presentation.api.schemas.policy import PolicyViewResponse

router = APIRouter(prefix="/api/policy", tags=["admin"], dependencies=AdminDeps)


def _to_response(view: PolicyView) -> PolicyViewResponse:
    data = view.model_dump()
    known = {stage.value for stage in StageName}
    grouped: dict[str, list[dict]] = {}
    for stage, rules in (data.get("rules_by_stage") or {}).items():
        if stage not in known:
            continue
        grouped[stage] = [
            {**rule, "stage": rule.get("stage") or stage}
            for rule in rules or []
            if isinstance(rule, dict)
        ]
    data["rules_by_stage"] = grouped
    try:
        return PolicyViewResponse.model_validate(data)
    except ValidationError:
        data["rules_by_stage"] = {}
        return PolicyViewResponse.model_validate(data)


@router.get("", response_model=PolicyViewResponse)
async def view_policy(container: ContainerDep) -> PolicyViewResponse:
    view = await container.policy_view.execute()
    return _to_response(view)


@router.post("/reload", response_model=PolicyViewResponse)
async def reload_policy(container: ContainerDep) -> PolicyViewResponse:
    view = await container.reload_policy.execute()
    return _to_response(view)
