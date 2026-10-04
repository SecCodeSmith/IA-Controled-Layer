from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from control_layer.domain.models.classifier import (
    CLASSIFIER_TRACE_KEY,
    FORCE_VERIFY_KEY,
    TRAINING_SAMPLE_KEY,
    ClassifierExplanation,
    ClassifierInfo,
    ClassifierTrace,
    LeafInfo,
    PathStep,
    RetrainResult,
    TrainedModel,
)

_NOW = datetime(2026, 10, 4, tzinfo=UTC)


def test_metadata_keys_are_distinct_strings() -> None:
    keys = {CLASSIFIER_TRACE_KEY, TRAINING_SAMPLE_KEY, FORCE_VERIFY_KEY}

    assert len(keys) == 3
    assert all(isinstance(key, str) and key for key in keys)


@pytest.mark.parametrize("direction", ["<=", ">"])
def test_path_step_accepts_both_directions(direction: str) -> None:
    step = PathStep(feature="ignore", value=0.4, threshold=0.2, direction=direction)

    assert step.direction == direction


def test_path_step_rejects_unknown_direction() -> None:
    with pytest.raises(ValidationError):
        PathStep(feature="ignore", value=0.4, threshold=0.2, direction="<")


def test_leaf_info_fraction_bounded() -> None:
    with pytest.raises(ValidationError):
        LeafInfo(node_id=3, samples=2, positive_fraction=1.5)


def test_explanation_defaults_for_non_tree_models() -> None:
    explanation = ClassifierExplanation(probability=0.3, model_type="logreg")

    assert explanation.path == []
    assert explanation.leaf is None
    assert explanation.top_features == []


def test_explanation_probability_bounded() -> None:
    with pytest.raises(ValidationError):
        ClassifierExplanation(probability=1.2, model_type="tree")


def test_explanation_with_path_and_leaf() -> None:
    explanation = ClassifierExplanation(
        probability=0.75,
        model_type="tree",
        path=[PathStep(feature="ignore", value=0.4, threshold=0.2, direction=">")],
        leaf=LeafInfo(node_id=7, samples=2, positive_fraction=1.0),
        top_features=["ignore"],
    )

    assert explanation.path[0].feature == "ignore"
    assert explanation.leaf is not None
    assert explanation.leaf.samples == 2


def test_classifier_info_unloaded_defaults() -> None:
    info = ClassifierInfo(loaded=False)

    assert info.path is None
    assert info.model_type is None
    assert info.version == 0
    assert info.trained_at is None
    assert info.f1 is None
    assert info.n_base == 0
    assert info.n_feedback == 0


@pytest.mark.parametrize("band", ["block", "escalate", "allow"])
def test_classifier_trace_bands(band: str) -> None:
    trace = ClassifierTrace(rule_id="prompt_injection_tree", probability=0.9, band=band)

    assert trace.band == band
    assert trace.sampled is False
    assert trace.forced is False
    assert trace.explanation is None


def test_classifier_trace_rejects_unknown_band() -> None:
    with pytest.raises(ValidationError):
        ClassifierTrace(rule_id="r", probability=0.9, band="maybe")


def test_retrain_result_round_trips_through_json() -> None:
    result = RetrainResult(
        f1=0.9,
        passed_gate=True,
        swapped=True,
        n_base=100,
        n_feedback=3,
        version=2,
        trained_at=_NOW,
    )

    assert RetrainResult.model_validate_json(result.model_dump_json()) == result


def test_trained_model_holds_an_opaque_estimator() -> None:
    estimator = object()

    model = TrainedModel(
        estimator=estimator,
        model_type="tree",
        f1=0.88,
        n_base=100,
        n_feedback=0,
        trained_at=_NOW,
    )

    assert model.estimator is estimator


def test_classifier_models_are_frozen() -> None:
    info = ClassifierInfo(loaded=True)

    with pytest.raises(ValidationError):
        info.loaded = False  # type: ignore[misc]
