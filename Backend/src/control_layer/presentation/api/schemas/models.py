from __future__ import annotations

from pydantic import BaseModel

from control_layer.domain.models.provider import ProviderInfo


class AvailableModelResponse(BaseModel):
    provider: str
    model: str
    allowed: bool
    size_gb: float | None = None


class ModelsResponse(BaseModel):
    active: ProviderInfo
    available: list[AvailableModelResponse]


class ModelSelectRequest(BaseModel):
    provider: str
    model: str
