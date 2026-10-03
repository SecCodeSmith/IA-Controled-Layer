from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from control_layer.domain.models.enums import StageName
from control_layer.domain.models.rule import Rule
from control_layer.domain.ports.policy_repository import PolicyRepository


class PolicyView(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: int
    status: str
    loaded_at: datetime | None = None
    source: str
    error: str | None = None
    raw_yaml: str
    document: dict
    rules_by_stage: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


def _rule_to_view_dict(rule: Rule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "type": rule.type,
        "action": rule.action.value,
        "on": [point.value for point in rule.on],
        "owasp": list(rule.owasp),
        "severity": rule.severity.value,
        "enabled": rule.enabled,
        "params": dict(rule.params),
    }


def _group_rules_by_stage(rules: list[Rule]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {stage.value: [] for stage in StageName.ordered()}
    for rule in rules:
        grouped[rule.stage.value].append(_rule_to_view_dict(rule))
    return grouped


class GetPolicyViewUseCase:
    def __init__(self, policy_repository: PolicyRepository) -> None:
        self._policy_repository = policy_repository

    async def execute(self) -> PolicyView:
        status = await self._policy_repository.status()
        document = await self._policy_repository.current()
        return PolicyView(
            version=status.get("version", document.version),
            status=status.get("status", "LOADED"),
            loaded_at=status.get("loaded_at"),
            source=status.get("source", ""),
            error=status.get("error"),
            raw_yaml=status.get("raw_yaml", ""),
            document=document.model_dump(mode="json"),
            rules_by_stage=_group_rules_by_stage(document.rules),
        )


class ReloadPolicyUseCase:
    def __init__(
        self, policy_repository: PolicyRepository, get_policy_view: GetPolicyViewUseCase | None = None
    ) -> None:
        self._policy_repository = policy_repository
        self._get_policy_view = get_policy_view or GetPolicyViewUseCase(policy_repository)

    async def execute(self) -> PolicyView:
        await self._policy_repository.reload()
        return await self._get_policy_view.execute()
