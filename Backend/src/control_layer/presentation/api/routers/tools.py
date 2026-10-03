from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from control_layer.domain.models.tool import ToolCallRequest
from control_layer.presentation.api.dependencies import BearerDep, ContainerDep, SessionDep
from control_layer.presentation.api.mappers import tool_outcome_response
from control_layer.presentation.api.schemas.tools import (
    ProvisionedToolItem,
    ToolCallRequestBody,
    ToolsListResponse,
)

router = APIRouter(prefix="/v1/tools", tags=["proxy"])


@router.get("", response_model=ToolsListResponse)
async def list_tools(
    token: BearerDep,
    session: SessionDep,
    container: ContainerDep,
    scope: Literal["provisioned", "all"] = "provisioned",
) -> ToolsListResponse:
    identity = await container.identity_service.resolve(token, session or "")
    tools = await container.list_tools.execute(identity, scope)
    return ToolsListResponse(
        tools=[
            ProvisionedToolItem(**tool.descriptor.model_dump(), provisioned=tool.provisioned)
            for tool in tools
        ]
    )


@router.post("/call")
async def call_tool(
    body: ToolCallRequestBody,
    token: BearerDep,
    session: SessionDep,
    container: ContainerDep,
) -> JSONResponse:
    identity = await container.identity_service.resolve(token, "")
    session_id = body.session_id or session or identity.sub
    request = ToolCallRequest(
        server=body.server, tool=body.tool, arguments=body.arguments, session_id=session_id
    )
    outcome = await container.tool_call.execute(token, session_id, request)
    return tool_outcome_response(outcome)
