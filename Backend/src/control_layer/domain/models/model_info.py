from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ModelInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    model: str
    size_gb: float | None = None
