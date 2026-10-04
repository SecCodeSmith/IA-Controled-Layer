from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from control_layer.application.events.feed_broadcaster import FeedBroadcaster
from control_layer.domain.ports.cache_repository import CacheRepository
from control_layer.domain.ports.explainable_classifier import ExplainablePromptClassifier
from control_layer.domain.ports.model_provider import ModelProvider
from control_layer.domain.ports.rule_evaluator import RuleEvaluator
from control_layer.domain.ports.sampler import Sampler
from control_layer.domain.ports.signature_feed import SignatureFeed
from control_layer.domain.ports.training_sample_repository import TrainingSampleRepository
from control_layer.infrastructure.settings import Settings
from control_layer.ml.classifier import NullPromptClassifier


@dataclass
class ClassifierModule:
    tree_classifier: ExplainablePromptClassifier
    sampler: Sampler | None
    samples: TrainingSampleRepository | None
    wrap_judge: Callable[[RuleEvaluator], RuleEvaluator]
    curation: object | None
    retrain_jobs: object | None
    status: object | None


def _unwrapped(inner: RuleEvaluator) -> RuleEvaluator:
    return inner


def build_classifier_module(
    settings: Settings,
    cache: CacheRepository,
    model_provider: ModelProvider,
    signature_feed: SignatureFeed,
    feed: FeedBroadcaster,
) -> ClassifierModule:
    return ClassifierModule(
        tree_classifier=NullPromptClassifier(),
        sampler=None,
        samples=None,
        wrap_judge=_unwrapped,
        curation=None,
        retrain_jobs=None,
        status=None,
    )
