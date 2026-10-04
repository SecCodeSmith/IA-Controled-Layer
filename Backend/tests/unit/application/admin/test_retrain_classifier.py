from __future__ import annotations

import builtins
from collections.abc import Sequence
from datetime import UTC, datetime

from control_layer.application.use_cases.admin.retrain_classifier import RetrainClassifierUseCase
from control_layer.domain.models.classifier import (
    ClassifierExplanation,
    ClassifierInfo,
    TrainedModel,
)
from control_layer.domain.models.training_sample import (
    SampleCounts,
    SampleSource,
    SampleStatus,
    TrainingSample,
)

_NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


class FakeTreeClassifier:
    def __init__(self, version: int) -> None:
        self.version = version

    def predict_proba(self, text: str) -> float:
        return 0.0

    def info(self) -> dict[str, object]:
        return {"loaded": True}

    def explain(self, text: str) -> ClassifierExplanation:
        return ClassifierExplanation(probability=0.0, model_type="tree")

    def describe(self) -> ClassifierInfo:
        return ClassifierInfo(loaded=True, model_type="tree", version=self.version)


class FakeSwitchable(FakeTreeClassifier):
    def __init__(self, version: int) -> None:
        super().__init__(version)
        self.swapped_to: list[FakeTreeClassifier] = []

    def swap(self, new: FakeTreeClassifier) -> None:
        self.swapped_to.append(new)
        self.version = new.version


class FakeTrainer:
    def __init__(self, f1: float) -> None:
        self.f1 = f1
        self.calls: list[tuple[list[TrainingSample], int]] = []
        self.published: list[int] = []

    def train(self, feedback: Sequence[TrainingSample], *, seed: int) -> TrainedModel:
        self.calls.append((list(feedback), seed))
        return TrainedModel(
            estimator=object(),
            model_type="tree",
            f1=self.f1,
            n_base=600,
            n_feedback=len(feedback),
            trained_at=_NOW,
        )

    def publish(self, model: TrainedModel, *, version: int) -> FakeTreeClassifier:
        self.published.append(version)
        return FakeTreeClassifier(version)


class FakeCache:
    def __init__(self) -> None:
        self.flushed: list[str] = []

    async def flush(self, prefix: str) -> None:
        self.flushed.append(prefix)


class InMemorySamples:
    def __init__(self, samples: list[TrainingSample]) -> None:
        self.samples = samples

    async def add(self, sample: TrainingSample) -> TrainingSample:
        return sample

    async def get(self, sample_id: str) -> TrainingSample | None:
        return None

    async def update(self, sample: TrainingSample) -> None:
        return None

    async def counts(self) -> SampleCounts:
        return SampleCounts()

    async def list(
        self, status: SampleStatus | None = None, limit: int = 100
    ) -> builtins.list[TrainingSample]:
        return [s for s in self.samples if status is None or s.status == status][:limit]


def _sample(sample_id: str, status: SampleStatus) -> TrainingSample:
    return TrainingSample(
        id=sample_id,
        text=f"text {sample_id}",
        label=1,
        source=SampleSource.judge,
        status=status,
        created_at=_NOW,
    )


_SAMPLES = [
    _sample("a1", SampleStatus.accepted),
    _sample("p1", SampleStatus.pending),
    _sample("r1", SampleStatus.rejected),
    _sample("a2", SampleStatus.accepted),
]


def _use_case(
    trainer: FakeTrainer, classifier: FakeSwitchable, cache: FakeCache
) -> RetrainClassifierUseCase:
    return RetrainClassifierUseCase(
        trainer, InMemorySamples(_SAMPLES), classifier, cache, min_f1=0.85
    )


async def test_passing_gate_publishes_next_version_swaps_and_flushes_decisions() -> None:
    trainer, classifier, cache = FakeTrainer(f1=0.9), FakeSwitchable(version=3), FakeCache()

    result = await _use_case(trainer, classifier, cache).execute()

    assert trainer.published == [4]
    assert [c.version for c in classifier.swapped_to] == [4]
    assert cache.flushed == ["decision:"]
    assert result.passed_gate is True
    assert result.swapped is True
    assert result.version == 4
    assert result.f1 == 0.9
    assert result.n_base == 600
    assert result.n_feedback == 2
    assert result.trained_at == _NOW


async def test_failing_gate_keeps_current_classifier() -> None:
    trainer, classifier, cache = FakeTrainer(f1=0.5), FakeSwitchable(version=3), FakeCache()

    result = await _use_case(trainer, classifier, cache).execute()

    assert trainer.published == []
    assert classifier.swapped_to == []
    assert cache.flushed == []
    assert result.passed_gate is False
    assert result.swapped is False
    assert result.version == 3


async def test_feedback_is_accepted_samples_only_by_default() -> None:
    trainer = FakeTrainer(f1=0.9)

    await _use_case(trainer, FakeSwitchable(0), FakeCache()).execute()

    feedback, seed = trainer.calls[0]
    assert {s.id for s in feedback} == {"a1", "a2"}
    assert seed == 42


async def test_include_pending_adds_pending_samples_and_seed_is_forwarded() -> None:
    trainer = FakeTrainer(f1=0.9)

    await _use_case(trainer, FakeSwitchable(0), FakeCache()).execute(
        include_pending=True, seed=7
    )

    feedback, seed = trainer.calls[0]
    assert {s.id for s in feedback} == {"a1", "a2", "p1"}
    assert seed == 7


async def test_progress_steps_are_reported_in_order() -> None:
    steps: list[str] = []

    async def progress(step: str) -> None:
        steps.append(step)

    await _use_case(FakeTrainer(f1=0.9), FakeSwitchable(0), FakeCache()).execute(
        progress=progress
    )

    assert steps == ["loading", "training", "evaluating", "publishing"]


async def test_failing_gate_stops_progress_before_publishing() -> None:
    steps: list[str] = []

    async def progress(step: str) -> None:
        steps.append(step)

    await _use_case(FakeTrainer(f1=0.1), FakeSwitchable(0), FakeCache()).execute(
        progress=progress
    )

    assert steps == ["loading", "training", "evaluating"]
