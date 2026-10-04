from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from control_layer.application.classifier.retrain_job_manager import RetrainJobManager
from control_layer.application.evaluators.policy.feedback_recording import (
    FeedbackRecordingEvaluator,
)
from control_layer.application.events.feed_broadcaster import FeedBroadcaster
from control_layer.application.services.dataset_curation_service import DatasetCurationService
from control_layer.application.use_cases.admin.classifier import ClassifierAdminUseCase
from control_layer.application.use_cases.admin.retrain_classifier import (
    RetrainClassifierUseCase,
)
from control_layer.domain.ports.cache_repository import CacheRepository
from control_layer.domain.ports.explainable_classifier import (
    ExplainablePromptClassifier,
    SwappableClassifier,
)
from control_layer.domain.ports.model_provider import ModelProvider
from control_layer.domain.ports.rule_evaluator import RuleEvaluator
from control_layer.domain.ports.sampler import Sampler
from control_layer.domain.ports.signature_feed import SignatureFeed
from control_layer.domain.ports.training_sample_repository import TrainingSampleRepository
from control_layer.infrastructure.ml.hash_sampler import HashSampler
from control_layer.infrastructure.ml.sklearn_tree_trainer import SklearnTreeTrainer
from control_layer.infrastructure.ml.switchable_classifier import SwitchableClassifier
from control_layer.infrastructure.repositories.jsonl_training_sample_repository import (
    JsonlTrainingSampleRepository,
)
from control_layer.infrastructure.settings import Settings
from control_layer.ml.classifier import NullPromptClassifier, SklearnPromptClassifier

logger = logging.getLogger(__name__)

JudgeWrapper = Callable[[RuleEvaluator], RuleEvaluator]


@dataclass
class ClassifierModule:
    tree_classifier: SwappableClassifier
    sampler: Sampler
    samples: TrainingSampleRepository
    wrap_judge: JudgeWrapper
    curation: DatasetCurationService
    retrain_jobs: RetrainJobManager
    status: ClassifierAdminUseCase


def _load_tree(settings: Settings) -> ExplainablePromptClassifier:
    try:
        return SklearnPromptClassifier.load(str(settings.ml_tree_path_resolved))
    except Exception as exc:
        logger.warning("Decision-tree classifier unavailable (%s); using null classifier", exc)
        return NullPromptClassifier()


def _build_samples(settings: Settings) -> TrainingSampleRepository:
    path = settings.training_samples_path_resolved
    path.parent.mkdir(parents=True, exist_ok=True)
    return JsonlTrainingSampleRepository(path)


def _judge_wrapper(samples: TrainingSampleRepository) -> JudgeWrapper:
    def wrap(inner: RuleEvaluator) -> RuleEvaluator:
        return FeedbackRecordingEvaluator(inner, samples)

    return wrap


def _build_retrain_jobs(
    settings: Settings,
    tree: SwappableClassifier,
    samples: TrainingSampleRepository,
    cache: CacheRepository,
    feed: FeedBroadcaster,
) -> RetrainJobManager:
    trainer = SklearnTreeTrainer(
        settings.ml_dataset_path_resolved,
        settings.ml_tree_supplement_path_resolved,
        settings.ml_tree_path_resolved,
        settings.retrain_min_f1,
    )
    use_case = RetrainClassifierUseCase(
        trainer, samples, tree, cache, min_f1=settings.retrain_min_f1
    )
    return RetrainJobManager(use_case, feed)


def build_classifier_module(
    settings: Settings,
    cache: CacheRepository,
    model_provider: ModelProvider,
    signature_feed: SignatureFeed,
    feed: FeedBroadcaster,
) -> ClassifierModule:
    tree = SwitchableClassifier(_load_tree(settings))
    samples = _build_samples(settings)
    curation = DatasetCurationService(
        model_provider, samples, signature_feed, settings.judge_model
    )
    retrain_jobs = _build_retrain_jobs(settings, tree, samples, cache, feed)
    return ClassifierModule(
        tree_classifier=tree,
        sampler=HashSampler(settings.verify_sample_salt),
        samples=samples,
        wrap_judge=_judge_wrapper(samples),
        curation=curation,
        retrain_jobs=retrain_jobs,
        status=ClassifierAdminUseCase(tree, samples, retrain_jobs, curation),
    )
