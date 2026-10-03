from __future__ import annotations

from control_layer.domain.models.budget_usage import BudgetUsage
from control_layer.domain.models.chat import Usage
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.ports.budget_repository import BudgetRepository


class BudgetService:
    def __init__(self, budget_repository: BudgetRepository) -> None:
        self._budget_repository = budget_repository

    async def record(
        self, identity: Identity, usage: Usage, model: str, policy: PolicyDocument
    ) -> BudgetUsage:
        pricing = policy.models.pricing.get(model)
        if pricing is None:
            cost_usd = 0.0
        else:
            cost_usd = (
                usage.prompt_tokens / 1000 * pricing.input_per_1k_usd
                + usage.completion_tokens / 1000 * pricing.output_per_1k_usd
            )
        return await self._budget_repository.record_usage(
            identity.sub, usage.total_tokens, cost_usd
        )
