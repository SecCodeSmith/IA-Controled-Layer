from __future__ import annotations

from typing import Protocol

from control_layer.domain.models.classifier import ClassifierExplanation, ClassifierInfo
from control_layer.domain.ports.prompt_classifier import PromptClassifier


class ExplainablePromptClassifier(PromptClassifier, Protocol):
    def explain(self, text: str) -> ClassifierExplanation: ...

    def describe(self) -> ClassifierInfo: ...


class SwappableClassifier(ExplainablePromptClassifier, Protocol):
    def swap(self, new: ExplainablePromptClassifier) -> None: ...
