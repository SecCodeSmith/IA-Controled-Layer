from __future__ import annotations

from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule
from control_layer.domain.models.tool import ToolDescriptor


class ResidencyEvaluator:
    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        descriptor: ToolDescriptor | None = ctx.metadata.get("tool_descriptor")
        if descriptor is None or descriptor.data_region is None or ctx.identity is None:
            return RuleOutcome(matched=False)

        location_config = policy.locations.get(descriptor.data_region)
        allowed_regions = location_config.allowed_regions if location_config else []
        if ctx.identity.region in allowed_regions:
            return RuleOutcome(matched=False)

        return RuleOutcome(
            matched=True,
            reason="Data residency: EU-only",
            evidence=[descriptor.data_region, ctx.identity.region],
        )
