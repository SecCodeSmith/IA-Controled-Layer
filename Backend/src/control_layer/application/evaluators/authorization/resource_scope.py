from __future__ import annotations

from control_layer.application.resources.scope_checker import ResourceScopeChecker
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.enums import InterceptionPoint
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule


class ResourceScopeEvaluator:
    def __init__(self) -> None:
        self._checker = ResourceScopeChecker()

    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        if (
            ctx.point is not InterceptionPoint.tool_call
            or ctx.tool_call is None
            or ctx.identity is None
        ):
            return RuleOutcome(matched=False)

        call = ctx.tool_call
        verdict = self._checker.check_call(
            policy, ctx.identity, call.server, call.tool, call.arguments
        )
        if verdict.allowed:
            return RuleOutcome(matched=False)

        evidence = [f"resource:{verdict.matched_resource_id}"]
        if verdict.pattern is not None:
            evidence.append(f"pattern:{verdict.pattern}")
        return RuleOutcome(matched=True, reason=verdict.rule_reason, evidence=evidence)
