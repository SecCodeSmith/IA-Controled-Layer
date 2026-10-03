from __future__ import annotations

import time
from collections.abc import Callable

from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule
from control_layer.domain.ports.cache_repository import CacheRepository

_COUNTER_TTL_S = 120
_WINDOW_S = 60
_BUCKET_S = 10


class RateLimitEvaluator:
    def __init__(self, cache: CacheRepository, clock: Callable[[], float] = time.time) -> None:
        self._cache = cache
        self._clock = clock

    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        if ctx.identity is None:
            return RuleOutcome(matched=False)

        count = await self._count_window(ctx.identity.sub)
        per_minute = rule.params.get("per_minute", 60)
        if count > per_minute:
            return RuleOutcome(matched=True, reason="Rate limit exceeded", evidence=[str(count)])
        return RuleOutcome(matched=False)

    async def _count_window(self, sub: str) -> int:
        bucket = int(self._clock()) // _BUCKET_S
        count = await self._cache.incr(f"rate:{sub}:{bucket}", ttl=_COUNTER_TTL_S)
        for age in range(1, _WINDOW_S // _BUCKET_S):
            earlier = await self._cache.get(f"rate:{sub}:{bucket - age}")
            if earlier is not None:
                count += int(earlier)
        return count
