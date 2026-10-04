from __future__ import annotations

from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.resource import WILDCARD_ROLE, ResourceMatch


def find_grant(policy: PolicyDocument, server: str, tool: str, role: str) -> ResourceMatch | None:
    resource = next((r for r in policy.resources if r.covers(server, tool)), None)
    if resource is None:
        return None
    grant = resource.roles.get(role)
    if grant is None:
        grant = resource.roles.get(WILDCARD_ROLE)
    return ResourceMatch(resource=resource, role=role, grant=grant)
