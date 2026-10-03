from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ProviderInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    model: str
