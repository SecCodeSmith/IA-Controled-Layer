from __future__ import annotations

from control_layer.application.evaluators._labels import role_label
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule
from control_layer.domain.models.tool import ToolDescriptor


class RbacEvaluator:
    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        descriptor: ToolDescriptor | None = ctx.metadata.get("tool_descriptor")
        if descriptor is None or ctx.identity is None:
            return RuleOutcome(matched=False)

        role_config = policy.roles.get(ctx.identity.role.value)
        allowed_servers = role_config.mcp_servers if role_config else []
        denied_tools = role_config.tools_deny if role_config else []

        provisioned = descriptor.server in allowed_servers
        denied = descriptor.qualified_name in denied_tools
        if provisioned and not denied:
            return RuleOutcome(matched=False)

        label = role_label(ctx.identity.role)
        return RuleOutcome(
            matched=True,
            reason=f"{descriptor.server} is not provisioned for the {label} role",
            evidence=[descriptor.qualified_name],
        )
