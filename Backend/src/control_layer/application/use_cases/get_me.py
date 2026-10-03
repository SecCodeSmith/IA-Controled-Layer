from __future__ import annotations

from control_layer.application.services.tool_catalog import ToolCatalog
from control_layer.application.use_cases.outcomes import MeView
from control_layer.domain.models.identity import Identity
from control_layer.domain.ports.budget_repository import BudgetRepository
from control_layer.domain.ports.model_provider import ModelProvider
from control_layer.domain.ports.policy_repository import PolicyRepository
from control_layer.domain.ports.risk_repository import RiskRepository


class GetMeUseCase:
    def __init__(
        self,
        tool_catalog: ToolCatalog,
        budget_repository: BudgetRepository,
        risk_repository: RiskRepository,
        policy_repository: PolicyRepository,
        model_provider: ModelProvider,
    ) -> None:
        self._tool_catalog = tool_catalog
        self._budget_repository = budget_repository
        self._risk_repository = risk_repository
        self._policy_repository = policy_repository
        self._model_provider = model_provider

    async def execute(self, identity: Identity) -> MeView:
        policy = await self._policy_repository.current()
        tools = await self._tool_catalog.provisioned_for(identity)
        budget = await self._budget_repository.get_usage(identity.sub)
        risk = await self._risk_repository.get(identity.sub)

        return MeView(
            identity=identity,
            tools=tools,
            policy_name=f"roles.{identity.role.value}",
            policy_version=policy.version,
            budget=budget,
            risk=risk,
            provider=self._model_provider.describe(),
        )
