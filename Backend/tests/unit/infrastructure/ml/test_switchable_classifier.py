from __future__ import annotations

from control_layer.domain.models.classifier import ClassifierExplanation, ClassifierInfo
from control_layer.infrastructure.ml.switchable_classifier import SwitchableClassifier


class FakeExplainableClassifier:
    def __init__(self, probability: float, model_type: str, version: int) -> None:
        self._probability = probability
        self._model_type = model_type
        self._version = version

    def predict_proba(self, text: str) -> float:
        return self._probability

    def explain(self, text: str) -> ClassifierExplanation:
        return ClassifierExplanation(probability=self._probability, model_type=self._model_type)

    def describe(self) -> ClassifierInfo:
        return ClassifierInfo(loaded=True, model_type=self._model_type, version=self._version)

    def info(self) -> dict[str, object]:
        return {"loaded": True, "path": self._model_type}


def test_forwards_every_call_to_the_initial_classifier() -> None:
    initial = FakeExplainableClassifier(0.3, "tree", 0)
    switchable = SwitchableClassifier(initial)

    assert switchable.predict_proba("text") == 0.3
    assert switchable.explain("text").model_type == "tree"
    assert switchable.describe().version == 0
    assert switchable.info() == {"loaded": True, "path": "tree"}
    assert switchable.current is initial


def test_swap_routes_later_calls_to_the_new_classifier() -> None:
    switchable = SwitchableClassifier(FakeExplainableClassifier(0.3, "tree", 0))
    replacement = FakeExplainableClassifier(0.9, "tree-v1", 1)

    switchable.swap(replacement)

    assert switchable.current is replacement
    assert switchable.predict_proba("text") == 0.9
    assert switchable.explain("text").probability == 0.9
    assert switchable.describe().version == 1
    assert switchable.info() == {"loaded": True, "path": "tree-v1"}
