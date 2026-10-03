from __future__ import annotations

from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule
from control_layer.domain.models.tool import ToolDescriptor
from control_layer.domain.ports.cache_repository import CacheRepository


class AnomalyEvaluator:
    def __init__(self, cache: CacheRepository) -> None:
        self._cache = cache

    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        descriptor: ToolDescriptor | None = ctx.metadata.get("tool_descriptor")
        if descriptor is None or ctx.identity is None or "destructive" not in descriptor.tags:
            return RuleOutcome(matched=False)

        key = f"seen:{ctx.identity.sub}:{descriptor.qualified_name}"
        existing = await self._cache.get(key)
        if existing is not None:
            return RuleOutcome(matched=False)

        await self._cache.set(key, "1")
        return RuleOutcome(matched=True, confidence=0.3, reason="First use of a destructive tool")
