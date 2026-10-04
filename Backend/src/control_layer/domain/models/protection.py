from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from control_layer.domain.models.enums import ProtectionMode


class ProtectionInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: ProtectionMode = ProtectionMode.enforce
    changed_at: datetime | None = None
    changed_by: str | None = None
