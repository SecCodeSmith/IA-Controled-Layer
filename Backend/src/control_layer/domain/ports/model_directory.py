from __future__ import annotations

from typing import Protocol

from control_layer.domain.models.model_info import ModelInfo


class ModelDirectory(Protocol):
    async def list_models(self) -> list[ModelInfo]: ...
