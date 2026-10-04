from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from control_layer.application.resources.path_scope import path_allowed
from control_layer.application.resources.resolver import find_grant
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.resource import ResourceMatch


class ScopeVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed: bool
    rule_reason: str | None = None
    pattern: str | None = None
    matched_resource_id: str | None = None


class ResourceScopeChecker:
    def check_call(
        self,
        policy: PolicyDocument,
        identity: Identity,
        server: str,
        tool: str,
        arguments: dict,
    ) -> ScopeVerdict:
        match = find_grant(policy, server, tool, identity.role.value)
        if match is None:
            return ScopeVerdict(allowed=True)
        if match.grant is None:
            return self._blocked(match, f"no resource grant for role '{match.role}'")
        return self._check_path(match, arguments)

    def _check_path(self, match: ResourceMatch, arguments: dict) -> ScopeVerdict:
        argument_name = match.resource.path_argument
        resource_id = match.resource.id
        if argument_name is None:
            return ScopeVerdict(allowed=True, matched_resource_id=resource_id)
        value = arguments.get(argument_name)
        if not isinstance(value, str) or not value:
            return self._blocked(match, f"missing path argument '{argument_name}'")
        decision = path_allowed(value, match.grant.paths)
        if decision.allowed:
            return ScopeVerdict(allowed=True, matched_resource_id=resource_id)
        return self._blocked(match, decision.reason, decision.pattern)

    @staticmethod
    def _blocked(match: ResourceMatch, reason: str, pattern: str | None = None) -> ScopeVerdict:
        return ScopeVerdict(
            allowed=False,
            rule_reason=reason,
            pattern=pattern,
            matched_resource_id=match.resource.id,
        )
