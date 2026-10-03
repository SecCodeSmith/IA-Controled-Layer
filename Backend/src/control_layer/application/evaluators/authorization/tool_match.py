from __future__ import annotations

from fnmatch import fnmatch

from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.enums import RuleAction
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule
from control_layer.domain.models.tool import ToolDescriptor


class ToolMatchEvaluator:
    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        descriptor: ToolDescriptor | None = ctx.metadata.get("tool_descriptor")
        if descriptor is None or ctx.tool_call is None or rule.match is None:
            return RuleOutcome(matched=False)

        patterns = rule.match.get("action", [])
        if isinstance(patterns, str):
            patterns = [patterns]
        name_matches = any(
            fnmatch(descriptor.name, pattern) or fnmatch(descriptor.qualified_name, pattern)
            for pattern in patterns
        )
        if not name_matches:
            return RuleOutcome(matched=False)

        server_pattern = rule.match.get("server")
        if server_pattern is not None and not fnmatch(descriptor.server, server_pattern):
            return RuleOutcome(matched=False)

        arg_patterns: dict = rule.match.get("args", {})
        for key, pattern in arg_patterns.items():
            value = str(ctx.tool_call.arguments.get(key, ""))
            if not fnmatch(value, pattern):
                return RuleOutcome(matched=False)

        if rule.action == RuleAction.require_approval:
            reason = "Destructive actions need your confirmation"
        else:
            reason = f"Tool call matches {rule.id}"

        return RuleOutcome(matched=True, reason=reason, evidence=[descriptor.qualified_name])
