from __future__ import annotations

import builtins
from datetime import UTC, datetime

from control_layer.application.use_cases.admin.classifier import ClassifierAdminUseCase
from control_layer.domain.models.classifier import (
    ClassifierExplanation,
    ClassifierInfo,
    RetrainResult,
)
from control_layer.domain.models.training_sample import (
    SampleCounts,
    SampleSource,
    SampleStatus,
    TrainingSample,
)

_NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
_INFO = ClassifierInfo(loaded=True, model_type="tree", version=2, f1=0.9)
_RESULT = RetrainResult(
    f1=0.9, passed_gate=True, swapped=True, n_base=600, n_feedback=1, version=2, trained_at=_NOW
)


class FakeClassifier:
    def predict_proba(self, text: str) -> float:
        return 0.0

    def info(self) -> dict[str, object]:
        return {"loaded": True}

    def explain(self, text: str) -> ClassifierExplanation:
        return ClassifierExplanation(probability=0.0, model_type="tree")

    def describe(self) -> ClassifierInfo:
        return _INFO


class FakeSamples:
    def __init__(self, samples: list[TrainingSample]) -> None:
        self.samples = samples
        self.list_calls: list[tuple[SampleStatus | None, int]] = []

    async def add(self, sample: TrainingSample) -> TrainingSample:
        return sample

    async def get(self, sample_id: str) -> TrainingSample | None:
        return None

    async def update(self, sample: TrainingSample) -> None:
        return None

    async def counts(self) -> SampleCounts:
        return SampleCounts(pending=2, accepted=1)

    async def list(
        self, status: SampleStatus | None = None, limit: int = 100
    ) -> builtins.list[TrainingSample]:
        self.list_calls.append((status, limit))
        return [s for s in self.samples if status is None or s.status == status][:limit]


class FakeRetrainJobs:
    running = True
    last_result = _RESULT


class FakeReviewer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int | None, SampleStatus | None, str]] = []

    async def review(
        self,
        sample_id: str,
        *,
        label: int | None = None,
        status: SampleStatus | None = None,
        reviewed_by: str = "admin",
    ) -> TrainingSample:
        self.calls.append((sample_id, label, status, reviewed_by))
        return _sample(sample_id, SampleStatus.accepted)


def _sample(sample_id: str, status: SampleStatus) -> TrainingSample:
    return TrainingSample(
        id=sample_id,
        text=f"text {sample_id}",
        label=1,
        source=SampleSource.judge,
        status=status,
        created_at=_NOW,
    )


def _use_case(samples: FakeSamples, reviewer: FakeReviewer) -> ClassifierAdminUseCase:
    return ClassifierAdminUseCase(FakeClassifier(), samples, FakeRetrainJobs(), reviewer)


async def test_status_combines_tree_counts_and_retrain_state() -> None:
    status = await _use_case(FakeSamples([]), FakeReviewer()).status()

    assert status.tree == _INFO
    assert status.counts == SampleCounts(pending=2, accepted=1)
    assert status.retrain_running is True
    assert status.last_retrain == _RESULT


async def test_list_samples_filters_by_status_and_limit() -> None:
    samples = FakeSamples(
        [_sample("p1", SampleStatus.pending), _sample("a1", SampleStatus.accepted)]
    )

    items = await _use_case(samples, FakeReviewer()).list_samples(SampleStatus.pending, 50)

    assert [s.id for s in items] == ["p1"]
    assert samples.list_calls == [(SampleStatus.pending, 50)]


async def test_patch_sample_delegates_to_reviewer_as_admin() -> None:
    reviewer = FakeReviewer()

    updated = await _use_case(FakeSamples([]), reviewer).patch_sample(
        "s1", label=0, status=SampleStatus.accepted
    )

    assert updated.id == "s1"
    assert reviewer.calls == [("s1", 0, SampleStatus.accepted, "admin")]
