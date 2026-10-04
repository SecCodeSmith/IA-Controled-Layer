from __future__ import annotations

import hashlib
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from control_layer.domain.models.enums import InterceptionPoint

MAX_SAMPLE_TEXT_CHARS = 2000


class SampleSource(StrEnum):
    judge = "judge"
    workbench = "workbench"
    curation = "curation"
    manual = "manual"


class SampleStatus(StrEnum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class TrainingSample(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    text: str = Field(min_length=1)
    label: Literal[0, 1]
    source: SampleSource
    status: SampleStatus = SampleStatus.pending
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    reason: str | None = None
    tree_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    point: InterceptionPoint | None = None
    call_id: str | None = None
    created_at: datetime
    reviewed_by: str | None = None

    @field_validator("text", mode="before")
    @classmethod
    def _truncate(cls, value: object) -> object:
        return value[:MAX_SAMPLE_TEXT_CHARS] if isinstance(value, str) else value

    @computed_field
    @property
    def text_sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


class SampleCounts(BaseModel):
    model_config = ConfigDict(frozen=True)

    pending: int = 0
    accepted: int = 0
    rejected: int = 0

    @computed_field
    @property
    def total(self) -> int:
        return self.pending + self.accepted + self.rejected
