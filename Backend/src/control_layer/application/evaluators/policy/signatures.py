from __future__ import annotations

import re

from control_layer.application.evaluators.policy._turn_text import injection_text
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule
from control_layer.domain.ports.signature_feed import SignatureFeed


class SignaturesEvaluator:
    def __init__(self, signature_feed: SignatureFeed) -> None:
        self._signature_feed = signature_feed

    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        categories = rule.params.get("categories")
        text = injection_text(ctx)

        for signature in await self._signature_feed.signatures():
            if categories and not set(signature.categories) & set(categories):
                continue
            if ctx.point not in signature.points:
                continue
            match = re.search(signature.pattern, text, re.IGNORECASE)
            if match is None:
                continue
            return RuleOutcome(
                matched=True,
                reason=f"Matched attack signature {signature.id}: {signature.title}",
                evidence=[match.group()],
            )

        return RuleOutcome(matched=False)
