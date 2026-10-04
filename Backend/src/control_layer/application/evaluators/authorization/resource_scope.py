from __future__ import annotations

from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule


class ResourceScopeEvaluator:
    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        return RuleOutcome(matched=False)
