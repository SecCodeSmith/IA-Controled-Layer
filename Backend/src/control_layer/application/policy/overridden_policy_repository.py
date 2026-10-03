from __future__ import annotations

from typing import Any

from control_layer.application.services.protection_service import ProtectionService
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule
from control_layer.domain.ports.policy_repository import PolicyRepository


class OverriddenPolicyRepository:
    def __init__(self, inner: PolicyRepository, protection: ProtectionService) -> None:
        self._inner = inner
        self._protection = protection

    async def current(self) -> PolicyDocument:
        return await self._apply(await self._inner.current())

    async def reload(self) -> PolicyDocument:
        return await self._apply(await self._inner.reload())

    async def status(self) -> dict[str, Any]:
        status = await self._inner.status()
        return {**status, "overrides": await self._protection.get_rule_overrides()}

    async def _apply(self, document: PolicyDocument) -> PolicyDocument:
        overrides = await self._protection.get_rule_overrides()
        if not overrides:
            return document
        rules = [self._with_override(rule, overrides) for rule in document.rules]
        return document.model_copy(update={"rules": rules})

    @staticmethod
    def _with_override(rule: Rule, overrides: dict[str, bool]) -> Rule:
        if rule.id not in overrides:
            return rule
        return rule.model_copy(update={"enabled": overrides[rule.id]})
