from __future__ import annotations

from control_layer.application.pipeline.stage_base import BaseStage
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import StageResult
from control_layer.domain.models.enums import InterceptionPoint, RuleAction, StageName
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.ports.budget_repository import BudgetRepository


class ResourceStage(BaseStage):
    def __init__(self, budget_repository: BudgetRepository) -> None:
        super().__init__(StageName.resource)
        self._budget_repository = budget_repository

    async def process(self, ctx: ProcessingContext, policy: PolicyDocument) -> StageResult:
        if ctx.point == InterceptionPoint.prompt:
            return await self._check_prompt_budget(ctx, policy)
        if ctx.point == InterceptionPoint.tool_call:
            return self._check_tool_quota(ctx, policy)
        return self.allow(0.0)

    async def _check_prompt_budget(self, ctx: ProcessingContext, policy: PolicyDocument) -> StageResult:
        if ctx.identity is None:
            return self.allow(0.0)

        budgets = policy.budgets
        usage = await self._budget_repository.get_usage(ctx.identity.sub)

        over_budget = (
            usage.tokens_used >= budgets.per_user_tokens
            or usage.cost_used_usd >= budgets.per_user_cost_usd
        )
        if over_budget:
            action = RuleAction.block if budgets.on_exceeded == "block" else RuleAction.flag
            return self.result(action, 0.0, reason="Token budget overrun")

        requested_max_tokens = ctx.metadata.get("max_tokens")
        if requested_max_tokens is not None and requested_max_tokens > budgets.max_tokens_per_request:
            ctx.metadata["max_tokens"] = budgets.max_tokens_per_request
            return self.result(
                RuleAction.flag,
                0.0,
                reason=f"max_tokens capped to {budgets.max_tokens_per_request}",
            )

        token_pct = (
            (usage.tokens_used / budgets.per_user_tokens * 100) if budgets.per_user_tokens else 0.0
        )
        cost_pct = (
            (usage.cost_used_usd / budgets.per_user_cost_usd * 100)
            if budgets.per_user_cost_usd
            else 0.0
        )
        pct = max(token_pct, cost_pct)
        if pct >= budgets.warn_at_percent:
            return self.result(RuleAction.flag, 0.0, reason=f"Budget at {pct:.0f}%")

        return self.allow(0.0)

    def _check_tool_quota(self, ctx: ProcessingContext, policy: PolicyDocument) -> StageResult:
        quota = policy.budgets.tool_calls_per_session
        if quota is None:
            return self.allow(0.0)

        session_state = ctx.metadata.get("session_state")
        used = len(session_state.call_hashes) if session_state is not None else 0
        if used >= quota:
            return self.result(
                RuleAction.block,
                0.0,
                reason=f"Tool call quota of {quota} per session exceeded",
            )
        return self.allow(0.0)
