from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from control_layer.domain.models.budgets import Budgets
from control_layer.domain.models.resource import ResourceConfig
from control_layer.domain.models.rule import Rule


class PricingEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_per_1k_usd: float
    output_per_1k_usd: float


class ModelsConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed: list[str] = Field(default_factory=list)
    pricing: dict[str, PricingEntry] = Field(default_factory=dict)


class RoleConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    mcp_servers: list[str] = Field(default_factory=list)
    tools_deny: list[str] = Field(default_factory=list)
    transaction_limit: float | None = None
    beneficiary_allowlist: list[str] = Field(default_factory=list)


class LocationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed_regions: list[str] = Field(default_factory=list)


class PolicyDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: int
    profile: str
    models: ModelsConfig
    roles: dict[str, RoleConfig]
    locations: dict[str, LocationConfig]
    rules: list[Rule]
    budgets: Budgets
    loaded_at: datetime
    source_hash: str
    resources: list[ResourceConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_resource_ids(self) -> PolicyDocument:
        seen: set[str] = set()
        for resource in self.resources:
            if resource.id in seen:
                raise ValueError(f"duplicate resource id: {resource.id}")
            seen.add(resource.id)
        return self
