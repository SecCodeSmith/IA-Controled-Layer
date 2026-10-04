from __future__ import annotations

from control_layer.application.services.tool_catalog import ToolCatalog
from control_layer.application.use_cases.admin.workbench_views import (
    ResourceMatrixView,
    ResourceView,
)
from control_layer.domain.models.enums import Role
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.resource import WILDCARD_ROLE, ResourceConfig
from control_layer.domain.ports.policy_repository import PolicyRepository

_INVENTORY_IDENTITY = Identity(
    sub="workbench-inventory",
    name="Workbench inventory",
    role=Role.developer,
    location="-",
    region="-",
    agent_id="workbench-inventory",
)


class ResourceMatrixUseCase:
    def __init__(self, policy_repository: PolicyRepository, tool_catalog: ToolCatalog) -> None:
        self._policy_repository = policy_repository
        self._tool_catalog = tool_catalog

    async def execute(self) -> ResourceMatrixView:
        policy = await self._policy_repository.current()
        tools_by_server = await self._tool_names_by_server()
        return ResourceMatrixView(
            roles=[role.value for role in Role] + [WILDCARD_ROLE],
            resources=[self._view(resource, tools_by_server) for resource in policy.resources],
        )

    async def _tool_names_by_server(self) -> dict[str, list[str]]:
        names: dict[str, list[str]] = {}
        for entry in await self._tool_catalog.all_tools(_INVENTORY_IDENTITY):
            names.setdefault(entry.descriptor.server, []).append(entry.descriptor.name)
        return names

    @staticmethod
    def _view(resource: ResourceConfig, tools_by_server: dict[str, list[str]]) -> ResourceView:
        return ResourceView(
            id=resource.id,
            server=resource.server,
            tools=list(resource.tools) or tools_by_server.get(resource.server, []),
            path_argument=resource.path_argument,
            records=resource.records,
            grants=dict(resource.roles),
        )
