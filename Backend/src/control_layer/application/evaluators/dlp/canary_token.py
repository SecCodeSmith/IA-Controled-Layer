from __future__ import annotations

from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule


class CanaryTokenEvaluator:
    def __init__(self, token: str) -> None:
        self._token = token

    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        if self._token and self._token in ctx.current_text:
            return RuleOutcome(
                matched=True, reason="System prompt canary leaked", evidence=[self._token]
            )
        return RuleOutcome(matched=False)
