from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from control_layer.domain.models.classifier import TrainedModel
from control_layer.domain.models.training_sample import TrainingSample
from control_layer.domain.ports.explainable_classifier import ExplainablePromptClassifier


class ClassifierTrainer(Protocol):
    def train(self, feedback: Sequence[TrainingSample], *, seed: int) -> TrainedModel: ...

    def publish(self, model: TrainedModel, *, version: int) -> ExplainablePromptClassifier: ...
