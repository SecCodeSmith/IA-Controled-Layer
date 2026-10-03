from __future__ import annotations

from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule
from control_layer.domain.ports.cache_repository import CacheRepository


class CircuitBreakerEvaluator:
    def __init__(self, cache: CacheRepository) -> None:
        self._cache = cache

    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        if ctx.identity is None:
            return RuleOutcome(matched=False)

        value = await self._cache.get(f"quarantine:{ctx.identity.sub}")
        if value is not None:
            return RuleOutcome(
                matched=True, reason="User quarantined after repeated blocked actions"
            )
        return RuleOutcome(matched=False)
