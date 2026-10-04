from __future__ import annotations

from control_layer.domain.models.classifier import ClassifierExplanation, ClassifierInfo
from control_layer.domain.ports.explainable_classifier import ExplainablePromptClassifier


class SwitchableClassifier:
    def __init__(self, initial: ExplainablePromptClassifier) -> None:
        self._active = initial

    @property
    def current(self) -> ExplainablePromptClassifier:
        return self._active

    def swap(self, new: ExplainablePromptClassifier) -> None:
        self._active = new

    def predict_proba(self, text: str) -> float:
        return self._active.predict_proba(text)

    def explain(self, text: str) -> ClassifierExplanation:
        return self._active.explain(text)

    def describe(self) -> ClassifierInfo:
        return self._active.describe()

    def info(self) -> dict[str, object]:
        return self._active.info()
