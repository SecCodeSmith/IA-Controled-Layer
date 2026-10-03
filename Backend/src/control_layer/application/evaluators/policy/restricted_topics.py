from __future__ import annotations

import re

from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule

_DEFAULT_PATTERNS: list[str] = [
    r"insider trading",
    r"money laundering",
    r"guaranteed returns?",
    r"tax evasion",
]


class RestrictedTopicsEvaluator:
    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        patterns = rule.params.get("patterns", _DEFAULT_PATTERNS)
        text = ctx.current_text

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match is not None:
                return RuleOutcome(
                    matched=True,
                    reason="Restricted financial topic",
                    evidence=[match.group()],
                )

        return RuleOutcome(matched=False)
