from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from control_layer.domain.models.enums import ProtectionMode


class ProtectionInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: ProtectionMode = ProtectionMode.enforce
