from __future__ import annotations

import time

from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule
from control_layer.domain.ports.cache_repository import CacheRepository

_COUNTER_TTL_S = 120


class RateLimitEvaluator:
    def __init__(self, cache: CacheRepository) -> None:
        self._cache = cache

    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        if ctx.identity is None:
            return RuleOutcome(matched=False)

        epoch_minute = int(time.time() // 60)
        key = f"rate:{ctx.identity.sub}:{epoch_minute}"
        count = await self._cache.incr(key, ttl=_COUNTER_TTL_S)

        per_minute = rule.params.get("per_minute", 60)
        if count > per_minute:
            return RuleOutcome(matched=True, reason="Rate limit exceeded", evidence=[str(count)])
        return RuleOutcome(matched=False)
