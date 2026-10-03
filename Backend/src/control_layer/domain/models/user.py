from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from control_layer.domain.models.enums import Role


class DemoUser(BaseModel):
    model_config = ConfigDict(frozen=True)

    sub: str
    name: str
    initials: str
    role: Role
    location: str
    region: str
    agent_id: str
    mcp_servers: list[str] = Field(default_factory=list)
    api_key: str | None = Field(default=None, repr=False)
