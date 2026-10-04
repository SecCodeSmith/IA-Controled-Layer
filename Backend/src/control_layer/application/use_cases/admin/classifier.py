from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from control_layer.domain.models.classifier import ClassifierInfo, RetrainResult
from control_layer.domain.models.training_sample import SampleCounts, SampleStatus, TrainingSample
from control_layer.domain.ports.explainable_classifier import ExplainablePromptClassifier
from control_layer.domain.ports.training_sample_repository import TrainingSampleRepository


class RetrainState(Protocol):
    @property
    def running(self) -> bool: ...

    @property
    def last_result(self) -> RetrainResult | None: ...


class SampleReviewer(Protocol):
    async def review(
        self,
        sample_id: str,
        *,
        label: int | None = None,
        status: SampleStatus | None = None,
        reviewed_by: str = "admin",
    ) -> TrainingSample: ...


class ClassifierStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    tree: ClassifierInfo
    counts: SampleCounts
    retrain_running: bool
    last_retrain: RetrainResult | None


class ClassifierAdminUseCase:
    def __init__(
        self,
        classifier: ExplainablePromptClassifier,
        repository: TrainingSampleRepository,
        retrain_jobs: RetrainState,
        curation: SampleReviewer,
    ) -> None:
        self._classifier = classifier
        self._repository = repository
        self._retrain_jobs = retrain_jobs
        self._curation = curation

    async def status(self) -> ClassifierStatus:
        return ClassifierStatus(
            tree=self._classifier.describe(),
            counts=await self._repository.counts(),
            retrain_running=self._retrain_jobs.running,
            last_retrain=self._retrain_jobs.last_result,
        )

    async def list_samples(
        self, status: SampleStatus | None = None, limit: int = 100
    ) -> list[TrainingSample]:
        return await self._repository.list(status, limit)

    async def patch_sample(
        self,
        sample_id: str,
        *,
        label: int | None = None,
        status: SampleStatus | None = None,
    ) -> TrainingSample:
        return await self._curation.review(
            sample_id, label=label, status=status, reviewed_by="admin"
        )
