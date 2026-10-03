from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from control_layer.domain.models.enums import StageName
from control_layer.domain.models.provider import ProviderInfo


class McpServerStatus(BaseModel):
    model_config = ConfigDict(frozen=True)
    error: str | None = None

    name: str
    status: str
    tools: int


class McpHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    servers: list[McpServerStatus] = Field(default_factory=list)


class CacheHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: str


class ClassifierStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    loaded: bool
    path: str | None = None


class PolicyStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: int
    status: str


class HealthView(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str = "ok"
    stages: list[str] = Field(default_factory=lambda: [s.value for s in StageName.ordered()])
    cache: CacheHealth
    mcp: McpHealth
    classifier: ClassifierStatus
    provider: ProviderInfo
    policy: PolicyStatus


class GetHealthUseCase:
    def execute(
        self,
        *,
        cache_mode: str,
        mcp_servers: list[McpServerStatus],
        classifier: ClassifierStatus,
        provider: ProviderInfo,
        policy_status: PolicyStatus,
    ) -> HealthView:
        return HealthView(
            cache=CacheHealth(mode=cache_mode),
            mcp=McpHealth(servers=mcp_servers),
            classifier=classifier,
            provider=provider,
            policy=policy_status,
        )
