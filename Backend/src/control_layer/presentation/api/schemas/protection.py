from __future__ import annotations

from pydantic import BaseModel

from control_layer.domain.models.enums import ProtectionMode


class ProtectionResponse(BaseModel):
    mode: ProtectionMode
    rule_overrides: dict[str, bool] = {}
    disabled_rules: list[str] = []


class ProtectionModeRequest(BaseModel):
    mode: ProtectionMode
