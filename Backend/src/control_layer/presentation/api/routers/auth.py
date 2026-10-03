from __future__ import annotations

from fastapi import APIRouter

from control_layer.presentation.api.dependencies import ContainerDep
from control_layer.presentation.api.schemas.auth import (
    TokenRequest,
    TokenResponse,
    UsersListResponse,
    UserSummary,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/users", response_model=UsersListResponse)
async def list_users(container: ContainerDep) -> UsersListResponse:
    users = await container.list_users.execute()
    return UsersListResponse(users=[UserSummary.model_validate(u.model_dump()) for u in users])


@router.post("/token", response_model=TokenResponse)
async def issue_token(body: TokenRequest, container: ContainerDep) -> TokenResponse:
    issued = await container.issue_token.execute(body.sub)
    return TokenResponse(
        access_token=issued.access_token,
        token_type=issued.token_type,
        expires_in=issued.expires_in,
        claims=issued.claims,
    )
