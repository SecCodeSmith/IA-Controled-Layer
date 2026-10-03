from __future__ import annotations

from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.enums import InterceptionPoint
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule


class ModelAllowlistEvaluator:
    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        if ctx.point != InterceptionPoint.prompt:
            return RuleOutcome(matched=False)

        model = ctx.metadata.get("model")
        if model is None:
            return RuleOutcome(matched=False)

        if model in policy.models.allowed:
            return RuleOutcome(matched=False)

        return RuleOutcome(
            matched=True,
            reason=f"Model {model} is not on the allowlist",
            evidence=[model],
        )
