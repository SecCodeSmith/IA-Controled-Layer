from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from control_layer.domain.exceptions import UnknownToolError
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.tool import ToolDescriptor
from control_layer.domain.ports.mcp_gateway import McpGateway
from control_layer.domain.ports.policy_repository import PolicyRepository


class ProvisionedTool(BaseModel):
    model_config = ConfigDict(frozen=True)

    descriptor: ToolDescriptor
    provisioned: bool


class ToolCatalog:
    def __init__(self, mcp_gateway: McpGateway, policy_repository: PolicyRepository) -> None:
        self._mcp_gateway = mcp_gateway
        self._policy_repository = policy_repository

    async def provisioned_for(self, identity: Identity) -> list[ToolDescriptor]:
        return [t.descriptor for t in await self.all_tools(identity) if t.provisioned]

    async def all_tools(self, identity: Identity) -> list[ProvisionedTool]:
        policy = await self._policy_repository.current()
        role_config = policy.roles.get(identity.role.value)
        allowed_servers = set(role_config.mcp_servers) if role_config else set()
        denied_tools = set(role_config.tools_deny) if role_config else set()

        return [
            ProvisionedTool(
                descriptor=descriptor,
                provisioned=descriptor.server in allowed_servers
                and descriptor.qualified_name not in denied_tools
                and self._region_allowed(descriptor, identity, policy),
            )
            for descriptor in await self._mcp_gateway.list_tools()
        ]

    @staticmethod
    def _region_allowed(
        descriptor: ToolDescriptor, identity: Identity, policy: PolicyDocument
    ) -> bool:
        if descriptor.data_region is None:
            return True
        location_config = policy.locations.get(descriptor.data_region)
        if location_config is None:
            return True
        return identity.region in location_config.allowed_regions

    async def descriptor(self, server: str, tool: str) -> ToolDescriptor:
        for candidate in await self._mcp_gateway.list_tools():
            if candidate.server == server and candidate.name == tool:
                return candidate
        raise UnknownToolError(server, tool)
