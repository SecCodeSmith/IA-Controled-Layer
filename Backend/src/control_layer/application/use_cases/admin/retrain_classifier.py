from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from control_layer.domain.models.classifier import RetrainResult, TrainedModel
from control_layer.domain.models.training_sample import SampleStatus, TrainingSample
from control_layer.domain.ports.cache_repository import CacheRepository
from control_layer.domain.ports.classifier_trainer import ClassifierTrainer
from control_layer.domain.ports.explainable_classifier import SwappableClassifier
from control_layer.domain.ports.training_sample_repository import TrainingSampleRepository

ProgressCallback = Callable[[str], Awaitable[None]]

_DECISION_CACHE_PREFIX = "decision:"
_ALL_SAMPLES = 1_000_000


async def _silent(step: str) -> None:
    return None


class RetrainClassifierUseCase:
    def __init__(
        self,
        trainer: ClassifierTrainer,
        repository: TrainingSampleRepository,
        classifier: SwappableClassifier,
        cache: CacheRepository,
        *,
        min_f1: float,
        seed_default: int = 42,
    ) -> None:
        self._trainer = trainer
        self._repository = repository
        self._classifier = classifier
        self._cache = cache
        self._min_f1 = min_f1
        self._seed_default = seed_default

    async def execute(
        self,
        include_pending: bool = False,
        seed: int | None = None,
        progress: ProgressCallback | None = None,
    ) -> RetrainResult:
        report = progress or _silent
        await report("loading")
        feedback = await self._feedback(include_pending)

        await report("training")
        model = await asyncio.to_thread(
            self._trainer.train, feedback, seed=self._seed_default if seed is None else seed
        )

        await report("evaluating")
        current_version = self._classifier.describe().version
        if model.f1 < self._min_f1:
            return _result(model, passed_gate=False, version=current_version)

        await report("publishing")
        next_version = current_version + 1
        published = await asyncio.to_thread(self._trainer.publish, model, version=next_version)
        self._classifier.swap(published)
        await self._cache.flush(_DECISION_CACHE_PREFIX)
        return _result(model, passed_gate=True, version=next_version)

    async def _feedback(self, include_pending: bool) -> list[TrainingSample]:
        statuses = [SampleStatus.accepted]
        if include_pending:
            statuses.append(SampleStatus.pending)
        feedback: list[TrainingSample] = []
        for status in statuses:
            feedback.extend(await self._repository.list(status, _ALL_SAMPLES))
        return feedback


def _result(model: TrainedModel, *, passed_gate: bool, version: int) -> RetrainResult:
    return RetrainResult(
        f1=model.f1,
        passed_gate=passed_gate,
        swapped=passed_gate,
        n_base=model.n_base,
        n_feedback=model.n_feedback,
        version=version,
        trained_at=model.trained_at,
    )
