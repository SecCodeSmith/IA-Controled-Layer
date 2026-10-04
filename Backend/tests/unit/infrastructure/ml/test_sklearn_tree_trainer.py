"""Tests for SklearnTreeTrainer."""
import json
from datetime import datetime
from pathlib import Path

import pytest

from control_layer.domain.models.training_sample import (
    SampleStatus,
    TrainingSample,
)
from control_layer.infrastructure.ml.sklearn_tree_trainer import SklearnTreeTrainer
from control_layer.ml.classifier import SklearnPromptClassifier


@pytest.fixture
def base_dataset_csv(tmp_path: Path) -> Path:
    """Create a minimal base dataset CSV."""
    path = tmp_path / "base.csv"
    path.write_text(
        'text,label,category\n'
        '"attack text 1",1,attack\n'
        '"benign text 1",0,benign\n'
        '"attack text 2",1,attack\n'
        '"benign text 2",0,benign\n'
        '"attack text 3",1,attack\n'
        '"benign text 3",0,benign\n'
        '"attack text 4",1,attack\n'
        '"benign text 4",0,benign\n'
        '"attack text 5",1,attack\n'
        '"benign text 5",0,benign\n'
    )
    return path


@pytest.fixture
def supplement_dataset_csv(tmp_path: Path) -> Path:
    """Create a supplement dataset CSV."""
    path = tmp_path / "supplement.csv"
    path.write_text(
        'text,label,category\n'
        '"benign operational 1",0,operational\n'
        '"benign operational 2",0,operational\n'
        '"benign operational 3",0,operational\n'
        '"benign operational 4",0,operational\n'
        '"benign operational 5",0,operational\n'
    )
    return path


def test_sklearn_tree_trainer_train_returns_trained_model(
    base_dataset_csv: Path, supplement_dataset_csv: Path, tmp_path: Path
) -> None:
    """Test that train returns a TrainedModel with correct counts."""
    artifact_path = tmp_path / "model.joblib"
    trainer = SklearnTreeTrainer(
        base_csv=base_dataset_csv,
        supplement_csv=supplement_dataset_csv,
        artifact_path=artifact_path,
        min_f1=0.5,
    )

    # Create feedback samples
    feedback_samples = [
        TrainingSample(
            id="f1",
            text="new attack pattern",
            label=1,
            source="judge",
            status=SampleStatus.accepted,
            confidence=0.9,
            reason="test",
            tree_probability=None,
            point=None,
            call_id="call1",
            created_at=datetime.utcnow(),
            reviewed_by=None,
        )
    ]

    trained_model = trainer.train(feedback_samples, seed=42)

    assert trained_model.estimator is not None
    assert trained_model.model_type == "tree"
    assert trained_model.f1 > 0.0
    assert trained_model.n_base == 10
    assert trained_model.n_feedback == 6  # 5 supplement + 1 feedback
    assert trained_model.trained_at is not None


def test_sklearn_tree_trainer_train_f1_above_gate(
    base_dataset_csv: Path, supplement_dataset_csv: Path, tmp_path: Path
) -> None:
    """Test that train achieves F1 above the gate."""
    artifact_path = tmp_path / "model.joblib"
    trainer = SklearnTreeTrainer(
        base_csv=base_dataset_csv,
        supplement_csv=supplement_dataset_csv,
        artifact_path=artifact_path,
        min_f1=0.5,
    )

    trained_model = trainer.train([], seed=42)

    # Should exceed min_f1
    assert trained_model.f1 >= 0.5


def test_sklearn_tree_trainer_publish_writes_joblib(
    base_dataset_csv: Path, supplement_dataset_csv: Path, tmp_path: Path
) -> None:
    """Test that publish writes the model to joblib."""
    artifact_path = tmp_path / "model.joblib"
    trainer = SklearnTreeTrainer(
        base_csv=base_dataset_csv,
        supplement_csv=supplement_dataset_csv,
        artifact_path=artifact_path,
        min_f1=0.5,
    )

    trained_model = trainer.train([], seed=42)
    trainer.publish(trained_model, version=0)

    assert artifact_path.exists()
    assert artifact_path.suffix == ".joblib"


def test_sklearn_tree_trainer_publish_writes_meta(
    base_dataset_csv: Path, supplement_dataset_csv: Path, tmp_path: Path
) -> None:
    """Test that publish writes metadata sidecar."""
    artifact_path = tmp_path / "model.joblib"
    trainer = SklearnTreeTrainer(
        base_csv=base_dataset_csv,
        supplement_csv=supplement_dataset_csv,
        artifact_path=artifact_path,
        min_f1=0.5,
    )

    trained_model = trainer.train([], seed=42)
    trainer.publish(trained_model, version=0)

    meta_path = artifact_path.with_suffix(".joblib.meta.json")
    assert meta_path.exists()

    with meta_path.open("r") as f:
        meta = json.load(f)

    assert meta["model_type"] == "tree"
    assert meta["f1"] == trained_model.f1
    assert meta["n_base"] == trained_model.n_base
    assert meta["n_feedback"] == trained_model.n_feedback
    assert meta["version"] == 0
    assert "trained_at" in meta


def test_sklearn_tree_trainer_publish_returns_classifier(
    base_dataset_csv: Path, supplement_dataset_csv: Path, tmp_path: Path
) -> None:
    """Test that publish returns a usable classifier."""
    artifact_path = tmp_path / "model.joblib"
    trainer = SklearnTreeTrainer(
        base_csv=base_dataset_csv,
        supplement_csv=supplement_dataset_csv,
        artifact_path=artifact_path,
        min_f1=0.5,
    )

    trained_model = trainer.train([], seed=42)
    classifier = trainer.publish(trained_model, version=0)

    assert isinstance(classifier, SklearnPromptClassifier)

    # Test that it can predict
    score = classifier.predict_proba("test text")
    assert 0.0 <= score <= 1.0


def test_sklearn_tree_trainer_publish_atomic(
    base_dataset_csv: Path, supplement_dataset_csv: Path, tmp_path: Path
) -> None:
    """Test that publish is atomic (no .tmp file left)."""
    artifact_path = tmp_path / "model.joblib"
    trainer = SklearnTreeTrainer(
        base_csv=base_dataset_csv,
        supplement_csv=supplement_dataset_csv,
        artifact_path=artifact_path,
        min_f1=0.5,
    )

    trained_model = trainer.train([], seed=42)
    trainer.publish(trained_model, version=0)

    # No .tmp file should exist after publish
    tmp_path_file = artifact_path.with_suffix(".joblib.tmp")
    assert not tmp_path_file.exists()


def test_sklearn_tree_trainer_train_with_feedback_increases_feedback_count(
    base_dataset_csv: Path, supplement_dataset_csv: Path, tmp_path: Path
) -> None:
    """Test that feedback samples are counted correctly."""
    artifact_path = tmp_path / "model.joblib"
    trainer = SklearnTreeTrainer(
        base_csv=base_dataset_csv,
        supplement_csv=supplement_dataset_csv,
        artifact_path=artifact_path,
        min_f1=0.5,
    )

    # Train without feedback
    trained_no_feedback = trainer.train([], seed=42)

    # Train with feedback
    feedback = [
        TrainingSample(
            id="f1",
            text="additional feedback",
            label=1,
            source="judge",
            status=SampleStatus.accepted,
            confidence=0.9,
            reason="test",
            tree_probability=None,
            point=None,
            call_id="call1",
            created_at=datetime.utcnow(),
            reviewed_by=None,
        )
    ]
    trained_with_feedback = trainer.train(feedback, seed=42)

    # Feedback count should increase by 1
    assert (
        trained_with_feedback.n_feedback == trained_no_feedback.n_feedback + 1
    )
