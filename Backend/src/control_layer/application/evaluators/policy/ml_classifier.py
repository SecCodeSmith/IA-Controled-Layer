from __future__ import annotations

import asyncio

from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule
from control_layer.domain.ports.prompt_classifier import PromptClassifier

_PROFILE_DEFAULTS: dict[str, tuple[float, float]] = {
    "strict": (0.7, 0.4),
    "balanced": (0.85, 0.5),
    "permissive": (0.95, 0.7),
}


class MlClassifierEvaluator:
    def __init__(self, classifier: PromptClassifier) -> None:
        self._classifier = classifier

    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        default_block, default_escalate = _PROFILE_DEFAULTS.get(
            policy.profile, _PROFILE_DEFAULTS["balanced"]
        )
        block_at = rule.params.get("block_at", default_block)
        escalate_at = rule.params.get("escalate_at", default_escalate)

        probability = await asyncio.to_thread(self._classifier.predict_proba, ctx.current_text)
        reason = f"Prompt-injection classifier score {probability:.2f}"

        if probability >= block_at:
            return RuleOutcome(matched=True, confidence=probability, reason=reason)
        if escalate_at <= probability < block_at:
            return RuleOutcome(
                matched=False, confidence=probability, inconclusive=True, reason=reason
            )
        return RuleOutcome(matched=False, confidence=probability, reason=reason)
