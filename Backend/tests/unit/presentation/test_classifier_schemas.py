from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from control_layer.domain.models.classifier import ClassifierInfo, RetrainResult
from control_layer.domain.models.training_sample import SampleCounts, SampleStatus
from control_layer.presentation.api.schemas.classifier import (
    ClassifierStatusResponse,
    CurateRequest,
    CurationSummary,
    RetrainJobResponse,
    RetrainRequest,
    SampleListResponse,
    SamplePatch,
)

_NOW = datetime(2026, 10, 4, tzinfo=UTC)


def test_status_response_shape() -> None:
    response = ClassifierStatusResponse(tree=ClassifierInfo(loaded=False), counts=SampleCounts())

    dumped = response.model_dump(mode="json")

    assert set(dumped) == {"tree", "counts", "retrain_running", "last_retrain"}
    assert dumped["retrain_running"] is False
    assert dumped["last_retrain"] is None
    assert dumped["counts"]["total"] == 0


def test_sample_list_defaults_empty() -> None:
    assert SampleListResponse().items == []


def test_sample_patch_accepts_label_or_status() -> None:
    assert SamplePatch(label=0).label == 0
    assert SamplePatch(status=SampleStatus.accepted).status == SampleStatus.accepted


def test_sample_patch_requires_at_least_one_field() -> None:
    with pytest.raises(ValidationError):
        SamplePatch()


def test_sample_patch_rejects_non_binary_label() -> None:
    with pytest.raises(ValidationError):
        SamplePatch(label=3)


def test_curate_request_default_and_bounds() -> None:
    assert CurateRequest().limit == 20
    with pytest.raises(ValidationError):
        CurateRequest(limit=0)


def test_curation_summary_defaults() -> None:
    summary = CurationSummary()

    assert summary.model_dump() == {
        "reviewed": 0,
        "accepted": 0,
        "rejected": 0,
        "relabelled": 0,
        "refused": 0,
        "error": None,
    }


def test_retrain_request_defaults() -> None:
    request = RetrainRequest()

    assert request.include_pending is False
    assert request.seed == 42


def test_retrain_job_response_with_result() -> None:
    result = RetrainResult(
        f1=0.9, passed_gate=True, swapped=True, n_base=10, n_feedback=1, version=1, trained_at=_NOW
    )

    job = RetrainJobResponse(job_id="j-1", status="complete", started_at=_NOW, result=result)

    assert job.finished_at is None
    assert job.error is None
    assert job.result == result


def test_retrain_job_response_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        RetrainJobResponse(job_id="j-1", status="paused", started_at=_NOW)
