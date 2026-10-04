from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from control_layer.domain.models.classifier import ClassifierInfo, RetrainResult
from control_layer.domain.models.training_sample import SampleCounts, SampleStatus, TrainingSample

RetrainJobStatus = Literal["running", "complete", "failed"]


class ClassifierStatusResponse(BaseModel):
    tree: ClassifierInfo
    counts: SampleCounts
    retrain_running: bool = False
    last_retrain: RetrainResult | None = None


class SampleListResponse(BaseModel):
    items: list[TrainingSample] = Field(default_factory=list)


class SamplePatch(BaseModel):
    label: Literal[0, 1] | None = None
    status: SampleStatus | None = None

    @model_validator(mode="after")
    def _requires_a_change(self) -> SamplePatch:
        if self.label is None and self.status is None:
            raise ValueError("provide at least one of 'label' or 'status'")
        return self


class CurateRequest(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)


class CurationSummary(BaseModel):
    reviewed: int = 0
    accepted: int = 0
    rejected: int = 0
    relabelled: int = 0
    refused: int = 0
    error: str | None = None


class RetrainRequest(BaseModel):
    include_pending: bool = False
    seed: int = 42


class RetrainJobResponse(BaseModel):
    job_id: str
    status: RetrainJobStatus
    started_at: datetime
    finished_at: datetime | None = None
    result: RetrainResult | None = None
    error: str | None = None
