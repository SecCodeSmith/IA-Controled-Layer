from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from control_layer.domain.models.enums import ProtectionMode


class ProtectionResponse(BaseModel):
    mode: ProtectionMode
    rule_overrides: dict[str, bool] = {}
    disabled_rules: list[str] = []
    changed_at: datetime | None = None
    changed_by: str | None = None


class ProtectionModeRequest(BaseModel):
    mode: ProtectionMode
