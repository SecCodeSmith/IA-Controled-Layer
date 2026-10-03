from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from control_layer.domain.models.enums import Role


class Identity(BaseModel):
    model_config = ConfigDict(frozen=True)

    sub: str
    name: str
    role: Role
    location: str
    region: str
    agent_id: str
    session_id: str | None = None


class TokenClaims(BaseModel):
    model_config = ConfigDict(frozen=True)

    sub: str
    name: str
    role: Role
    location: str
    region: str
    agent_id: str
    iss: str = "control-layer-mock-sso"
    iat: int
    exp: int
