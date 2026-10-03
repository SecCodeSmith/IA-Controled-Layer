from __future__ import annotations

from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.enums import InterceptionPoint
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value)


class TransactionLimitEvaluator:
    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        if ctx.point != InterceptionPoint.tool_call or ctx.tool_call is None:
            return RuleOutcome(matched=False)
        if ctx.identity is None:
            return RuleOutcome(matched=False)

        target_tool = rule.params.get("tool", "payments.transfer")
        if ctx.tool_call.qualified_name != target_tool:
            return RuleOutcome(matched=False)

        role_config = policy.roles.get(ctx.identity.role.value)
        if role_config is None:
            return RuleOutcome(matched=False)

        amount = ctx.tool_call.arguments.get("amount")
        limit = role_config.transaction_limit
        if amount is not None and limit is not None and amount > limit:
            return RuleOutcome(
                matched=True,
                reason=(
                    f"Transfer of {_format_number(amount)} exceeds the "
                    f"{_format_number(limit)} limit"
                ),
                evidence=[str(amount)],
            )

        beneficiary = ctx.tool_call.arguments.get("beneficiary")
        allowlist = role_config.beneficiary_allowlist
        if allowlist and beneficiary is not None and beneficiary not in allowlist:
            return RuleOutcome(
                matched=True,
                reason="Beneficiary not on the allowlist",
                evidence=[str(beneficiary)],
            )

        return RuleOutcome(matched=False)
