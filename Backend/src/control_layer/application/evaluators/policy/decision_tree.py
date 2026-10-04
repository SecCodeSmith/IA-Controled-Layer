from __future__ import annotations

import asyncio

from control_layer.domain.models.classifier import (
    CLASSIFIER_TRACE_KEY,
    FORCE_VERIFY_KEY,
    ClassifierBand,
    ClassifierExplanation,
    ClassifierTrace,
)
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule
from control_layer.domain.ports.explainable_classifier import ExplainablePromptClassifier
from control_layer.domain.ports.sampler import Sampler

_PROFILE_DEFAULTS: dict[str, tuple[float, float]] = {
    "strict": (0.7, 0.4),
    "balanced": (0.85, 0.5),
    "permissive": (0.95, 0.7),
}
_DEFAULT_SAMPLE_RATE = 0.2
_SAMPLED_REASON = "tree positive sampled for judge verification"
_FORCED_REASON = "tree verdict forced to judge"
_NULL_EXPLANATION = ClassifierExplanation(probability=0.0, model_type="null")


class DecisionTreeEvaluator:
    def __init__(
        self, classifier: ExplainablePromptClassifier | None, sampler: Sampler | None
    ) -> None:
        self._classifier = classifier
        self._sampler = sampler

    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        text = ctx.current_text
        explanation = await asyncio.to_thread(self._explain, text)
        probability = explanation.probability
        band = self._band(rule, policy, probability)
        forced = bool(ctx.metadata.get(FORCE_VERIFY_KEY))
        sampled = band == "block" and not forced and self._sampled(rule, ctx, text)

        ctx.metadata[CLASSIFIER_TRACE_KEY] = ClassifierTrace(
            rule_id=rule.id,
            probability=probability,
            band=band,
            sampled=sampled,
            forced=forced,
            explanation=explanation,
        )
        return self._outcome(band, probability, sampled=sampled, forced=forced)

    def _explain(self, text: str) -> ClassifierExplanation:
        if self._classifier is None:
            return _NULL_EXPLANATION
        probability = self._classifier.predict_proba(text)
        explanation = self._classifier.explain(text)
        return explanation.model_copy(update={"probability": probability})

    @staticmethod
    def _band(rule: Rule, policy: PolicyDocument, probability: float) -> ClassifierBand:
        default_block, default_escalate = _PROFILE_DEFAULTS.get(
            policy.profile, _PROFILE_DEFAULTS["balanced"]
        )
        if probability >= rule.params.get("block_at", default_block):
            return "block"
        if probability >= rule.params.get("escalate_at", default_escalate):
            return "escalate"
        return "allow"

    def _sampled(self, rule: Rule, ctx: ProcessingContext, text: str) -> bool:
        if self._sampler is None:
            return False
        rate = rule.params.get("verify_sample_rate", _DEFAULT_SAMPLE_RATE)
        return self._sampler.should_sample(rate, f"{rule.id}|{ctx.point.value}|{text}")

    @staticmethod
    def _outcome(
        band: ClassifierBand, probability: float, *, sampled: bool, forced: bool
    ) -> RuleOutcome:
        matched = band == "block"
        if forced:
            return RuleOutcome(
                matched=matched, confidence=probability, inconclusive=True, reason=_FORCED_REASON
            )
        if sampled:
            return RuleOutcome(
                matched=True, confidence=probability, inconclusive=True, reason=_SAMPLED_REASON
            )
        return RuleOutcome(
            matched=matched,
            confidence=probability,
            inconclusive=band == "escalate",
            reason=f"Decision-tree classifier score {probability:.2f}",
        )
