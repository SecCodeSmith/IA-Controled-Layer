from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from control_layer.domain.models.provider import ProviderInfo


class McpServerHealth(BaseModel):
    name: str
    status: str
    tools: int
    error: str | None = None


class McpHealth(BaseModel):
    servers: list[McpServerHealth] = []


class CacheHealth(BaseModel):
    mode: Literal["redis", "memory"]


class ClassifierHealth(BaseModel):
    loaded: bool
    path: str | None = None


class PolicyHealth(BaseModel):
    version: int
    status: Literal["LOADED", "ERROR"]


class HealthResponse(BaseModel):
    status: str = "ok"
    stages: list[str]
    cache: CacheHealth
    mcp: McpHealth
    classifier: ClassifierHealth
    provider: ProviderInfo
    policy: PolicyHealth
