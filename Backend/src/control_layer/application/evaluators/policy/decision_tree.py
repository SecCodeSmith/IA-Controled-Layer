from __future__ import annotations

from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule
from control_layer.domain.ports.explainable_classifier import ExplainablePromptClassifier
from control_layer.domain.ports.sampler import Sampler


class DecisionTreeEvaluator:
    def __init__(
        self, classifier: ExplainablePromptClassifier | None, sampler: Sampler | None
    ) -> None:
        self._classifier = classifier
        self._sampler = sampler

    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        return RuleOutcome(matched=False)
