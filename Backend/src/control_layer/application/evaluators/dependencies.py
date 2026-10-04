from __future__ import annotations

from dataclasses import dataclass

from control_layer.domain.ports.cache_repository import CacheRepository
from control_layer.domain.ports.explainable_classifier import ExplainablePromptClassifier
from control_layer.domain.ports.model_provider import ModelProvider
from control_layer.domain.ports.prompt_classifier import PromptClassifier
from control_layer.domain.ports.sampler import Sampler
from control_layer.domain.ports.signature_feed import SignatureFeed


@dataclass(frozen=True, slots=True)
class EvaluatorDependencies:
    cache: CacheRepository
    signature_feed: SignatureFeed
    classifier: PromptClassifier
    model_provider: ModelProvider
    canary_token: str
    judge_model: str
    tree_classifier: ExplainablePromptClassifier | None = None
    sampler: Sampler | None = None
