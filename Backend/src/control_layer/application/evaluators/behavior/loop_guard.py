from __future__ import annotations

import hashlib
import json

from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule
from control_layer.domain.ports.cache_repository import CacheRepository


class LoopGuardEvaluator:
    def __init__(self, cache: CacheRepository) -> None:
        self._cache = cache

    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        if ctx.tool_call is None:
            return RuleOutcome(matched=False)

        canonical_args = json.dumps(ctx.tool_call.arguments, sort_keys=True, separators=(",", ":"))
        fingerprint = ctx.tool_call.qualified_name + canonical_args
        digest = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
        key = f"loop:{ctx.session_id}:{digest}"

        window_s = rule.params.get("window_s", 60)
        count = await self._cache.incr(key, ttl=window_s)

        identical_calls = rule.params.get("identical_calls", 5)
        if count > identical_calls:
            return RuleOutcome(
                matched=True,
                reason="Repeated identical tool call, possible runaway loop",
                evidence=[str(count)],
            )
        return RuleOutcome(matched=False)
