from __future__ import annotations

from typing import Protocol

from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule


class RuleEvaluator(Protocol):
    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome: ...
