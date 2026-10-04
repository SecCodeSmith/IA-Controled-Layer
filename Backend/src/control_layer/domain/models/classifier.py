from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CLASSIFIER_TRACE_KEY = "classifier_trace"
TRAINING_SAMPLE_KEY = "training_sample_id"
FORCE_VERIFY_KEY = "force_verify"

ClassifierBand = Literal["block", "escalate", "allow"]


class PathStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    feature: str
    value: float
    threshold: float
    direction: Literal["<=", ">"]


class LeafInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    node_id: int
    samples: int = Field(ge=0)
    positive_fraction: float = Field(ge=0.0, le=1.0)


class ClassifierExplanation(BaseModel):
    model_config = ConfigDict(frozen=True)

    probability: float = Field(ge=0.0, le=1.0)
    model_type: str
    path: list[PathStep] = Field(default_factory=list)
    leaf: LeafInfo | None = None
    top_features: list[str] = Field(default_factory=list)


class ClassifierInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    loaded: bool
    path: str | None = None
    model_type: str | None = None
    version: int = 0
    trained_at: datetime | None = None
    f1: float | None = None
    n_base: int = 0
    n_feedback: int = 0


class ClassifierTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str
    probability: float = Field(ge=0.0, le=1.0)
    band: ClassifierBand
    sampled: bool = False
    forced: bool = False
    explanation: ClassifierExplanation | None = None


class RetrainResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    f1: float
    passed_gate: bool
    swapped: bool
    n_base: int
    n_feedback: int
    version: int
    trained_at: datetime


class TrainedModel(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    estimator: object
    model_type: str
    f1: float
    n_base: int
    n_feedback: int
    trained_at: datetime
