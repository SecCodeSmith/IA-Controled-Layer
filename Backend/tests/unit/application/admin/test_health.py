from __future__ import annotations

from control_layer.application.use_cases.admin.health import (
    ClassifierStatus,
    GetHealthUseCase,
    McpServerStatus,
    PolicyStatus,
)
from control_layer.domain.models.enums import StageName
from control_layer.domain.models.provider import ProviderInfo


async def test_health_view_lists_stages_in_fixed_order() -> None:
    use_case = GetHealthUseCase()

    view = use_case.execute(
        cache_mode="redis",
        mcp_servers=[McpServerStatus(name="github", status="connected", tools=4)],
        classifier=ClassifierStatus(loaded=True, path="artifacts/model.joblib"),
        provider=ProviderInfo(name="ollama", model="qwen2.5:7b"),
        policy_status=PolicyStatus(version=3, status="LOADED"),
    )

    assert view.status == "ok"
    assert view.stages == [s.value for s in StageName.ordered()]


async def test_health_view_carries_through_every_computed_input() -> None:
    use_case = GetHealthUseCase()

    view = use_case.execute(
        cache_mode="memory",
        mcp_servers=[McpServerStatus(name="github", status="connected", tools=4)],
        classifier=ClassifierStatus(loaded=False, path=None),
        provider=ProviderInfo(name="mock", model="mock"),
        policy_status=PolicyStatus(version=1, status="ERROR"),
    )

    assert view.cache.mode == "memory"
    assert view.mcp.servers[0].name == "github"
    assert view.mcp.servers[0].tools == 4
    assert view.classifier.loaded is False
    assert view.provider.name == "mock"
    assert view.policy.version == 1
    assert view.policy.status == "ERROR"
