from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from control_layer.application.services.protection_service import ProtectionService
from control_layer.domain.exceptions import RuleNotFoundError
from control_layer.domain.models.enums import ProtectionMode
from control_layer.domain.ports.policy_repository import PolicyRepository


class ProtectionView(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: ProtectionMode
    rule_overrides: dict[str, bool] = Field(default_factory=dict)
    disabled_rules: list[str] = Field(default_factory=list)


class RuleOverrideView(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str
    enabled: bool
    overridden: bool = True


class ManageProtectionUseCase:
    def __init__(self, protection: ProtectionService, policy_repository: PolicyRepository) -> None:
        self._protection = protection
        self._policy_repository = policy_repository

    async def get(self) -> ProtectionView:
        policy = await self._policy_repository.current()
        return ProtectionView(
            mode=await self._protection.get_mode(),
            rule_overrides=await self._protection.get_rule_overrides(),
            disabled_rules=[rule.id for rule in policy.rules if not rule.enabled],
        )

    async def set_mode(self, mode: ProtectionMode) -> ProtectionView:
        await self._protection.set_mode(mode)
        return await self.get()

    async def set_rule(self, rule_id: str, enabled: bool) -> RuleOverrideView:
        policy = await self._policy_repository.current()
        if all(rule.id != rule_id for rule in policy.rules):
            raise RuleNotFoundError(rule_id)
        await self._protection.set_rule_override(rule_id, enabled)
        return RuleOverrideView(rule_id=rule_id, enabled=enabled)

    async def clear_overrides(self) -> ProtectionView:
        await self._protection.clear_overrides()
        return await self.get()
