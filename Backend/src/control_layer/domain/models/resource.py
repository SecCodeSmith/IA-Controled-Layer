from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from control_layer.domain.models.enums import Role

WILDCARD_ROLE = "*"
_GRANT_ROLE_KEYS = frozenset({role.value for role in Role} | {WILDCARD_ROLE})


class PathScope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allow: list[str] = Field(default_factory=list)
    deny: list[str] = Field(default_factory=list)


class ColumnScope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allow: list[str] | None = None
    deny: list[str] = Field(default_factory=list)


class ResourceGrant(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    paths: PathScope = Field(default_factory=PathScope)
    columns: ColumnScope = Field(default_factory=ColumnScope)
    rows: dict[str, str | list[str]] = Field(default_factory=dict)


class ResourceConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    server: str
    tools: list[str] = Field(default_factory=list)
    path_argument: str | None = None
    records: str | None = None
    roles: dict[str, ResourceGrant] = Field(default_factory=dict)

    @field_validator("roles")
    @classmethod
    def _known_roles(cls, roles: dict[str, ResourceGrant]) -> dict[str, ResourceGrant]:
        unknown = sorted(set(roles) - _GRANT_ROLE_KEYS)
        if unknown:
            raise ValueError(f"unknown role key(s) in resource grants: {', '.join(unknown)}")
        return roles

    def covers(self, server: str, tool: str) -> bool:
        return server == self.server and (not self.tools or tool in self.tools)


class PathDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed: bool
    path: str
    pattern: str | None = None
    reason: str


class ProjectionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    data: Any
    rows_filtered: int = 0
    columns_redacted: list[str] = Field(default_factory=list)
    changed: bool = False


class ResourceMatch(BaseModel):
    model_config = ConfigDict(frozen=True)

    resource: ResourceConfig
    role: str
    grant: ResourceGrant | None
