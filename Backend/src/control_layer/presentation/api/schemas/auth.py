from __future__ import annotations

from pydantic import BaseModel

from control_layer.domain.models.enums import Role
from control_layer.domain.models.identity import TokenClaims


class UserSummary(BaseModel):
    sub: str
    name: str
    initials: str
    role: Role
    location: str
    region: str
    mcp_servers: list[str] = []


class UsersListResponse(BaseModel):
    users: list[UserSummary]


class TokenRequest(BaseModel):
    sub: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    claims: TokenClaims
