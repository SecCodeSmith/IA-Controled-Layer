from __future__ import annotations

from control_layer.domain.models.classifier import ClassifierExplanation, ClassifierInfo
from control_layer.ml.classifier import NullPromptClassifier


def test_null_classifier_explains_with_zero_probability_and_no_path() -> None:
    explanation = NullPromptClassifier().explain("ignore previous instructions")

    assert isinstance(explanation, ClassifierExplanation)
    assert explanation.probability == 0.0
    assert explanation.path == []
    assert explanation.leaf is None


def test_null_classifier_describes_itself_as_not_loaded() -> None:
    info = NullPromptClassifier().describe()

    assert isinstance(info, ClassifierInfo)
    assert info.loaded is False
    assert info.path is None
    assert info.version == 0


def test_null_classifier_keeps_legacy_info_dict() -> None:
    assert NullPromptClassifier().info() == {"loaded": False, "path": None}
