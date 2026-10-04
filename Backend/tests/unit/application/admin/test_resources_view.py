from __future__ import annotations

from datetime import UTC, datetime

from control_layer.application.services.tool_catalog import ProvisionedTool
from control_layer.application.use_cases.admin.resources_view import ResourceMatrixUseCase
from control_layer.domain.models.budgets import Budgets
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.policy import ModelsConfig, PolicyDocument
from control_layer.domain.models.resource import (
    ColumnScope,
    PathScope,
    ResourceConfig,
    ResourceGrant,
)
from control_layer.domain.models.tool import ToolDescriptor


def _descriptor(server: str, name: str) -> ToolDescriptor:
    return ToolDescriptor(
        server=server,
        name=name,
        qualified_name=f"{server}.{name}",
        description=name,
        scope="read",
    )


class FakeToolCatalog:
    def __init__(self, descriptors: list[ToolDescriptor]) -> None:
        self._descriptors = descriptors
        self.identities: list[Identity] = []

    async def all_tools(self, identity: Identity) -> list[ProvisionedTool]:
        self.identities.append(identity)
        return [ProvisionedTool(descriptor=d, provisioned=False) for d in self._descriptors]


class FakePolicyRepository:
    def __init__(self, resources: list[ResourceConfig]) -> None:
        self._document = PolicyDocument(
            version=1,
            profile="balanced",
            models=ModelsConfig(),
            roles={},
            locations={},
            rules=[],
            budgets=Budgets(
                per_user_tokens=1,
                per_user_cost_usd=1.0,
                max_tokens_per_request=1,
                upstream_timeout_s=1,
                warn_at_percent=80,
                on_exceeded="block",
            ),
            loaded_at=datetime.now(UTC),
            source_hash="h",
            resources=resources,
        )

    async def current(self) -> PolicyDocument:
        return self._document


def _use_case(resources: list[ResourceConfig], descriptors: list[ToolDescriptor]):
    return ResourceMatrixUseCase(FakePolicyRepository(resources), FakeToolCatalog(descriptors))


async def test_roles_list_every_role_plus_wildcard() -> None:
    response = await _use_case([], []).execute()

    assert response.roles == ["developer", "hr", "finance", "*"]
    assert response.resources == []


async def test_resource_fields_and_grants_are_copied() -> None:
    grant = ResourceGrant(
        paths=PathScope(allow=["src/**"], deny=["**/.env"]),
        columns=ColumnScope(allow=["name"]),
        rows={"department": "engineering"},
    )
    resource = ResourceConfig(
        id="github_repo_files",
        server="github",
        tools=["read_file"],
        path_argument="path",
        records="rows",
        roles={"developer": grant},
    )

    response = await _use_case([resource], []).execute()

    [view] = response.resources
    assert view.id == "github_repo_files"
    assert view.server == "github"
    assert view.tools == ["read_file"]
    assert view.path_argument == "path"
    assert view.records == "rows"
    assert view.grants == {"developer": grant}


async def test_empty_tools_expand_to_every_tool_of_the_server() -> None:
    resource = ResourceConfig(id="hr_rows", server="hr")
    descriptors = [
        _descriptor("hr", "list_employees"),
        _descriptor("github", "read_file"),
        _descriptor("hr", "get_employee"),
    ]

    response = await _use_case([resource], descriptors).execute()

    assert response.resources[0].tools == ["list_employees", "get_employee"]


async def test_explicit_tools_are_not_expanded() -> None:
    resource = ResourceConfig(id="files", server="github", tools=["read_file"])
    descriptors = [_descriptor("github", "read_file"), _descriptor("github", "push")]

    response = await _use_case([resource], descriptors).execute()

    assert response.resources[0].tools == ["read_file"]


async def test_server_without_catalog_tools_yields_empty_tool_list() -> None:
    response = await _use_case([ResourceConfig(id="x", server="ghost")], []).execute()

    assert response.resources[0].tools == []


async def test_resources_keep_policy_order() -> None:
    resources = [ResourceConfig(id="b", server="s"), ResourceConfig(id="a", server="s")]

    response = await _use_case(resources, []).execute()

    assert [r.id for r in response.resources] == ["b", "a"]
