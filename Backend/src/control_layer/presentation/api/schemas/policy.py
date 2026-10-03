from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from control_layer.domain.models.rule import Rule


class RuleView(Rule):
    overridden: bool = False


class PolicyViewResponse(BaseModel):
    version: int
    status: Literal["LOADED", "ERROR"]
    loaded_at: datetime | None = None
    source: str
    error: str | None = None
    raw_yaml: str
    document: dict
    rules_by_stage: dict[str, list[RuleView]] = {}


class RuleOverrideRequest(BaseModel):
    enabled: bool


class RuleOverrideResponse(BaseModel):
    rule_id: str
    enabled: bool
    overridden: bool = True
