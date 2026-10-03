from __future__ import annotations

from datetime import UTC, datetime

from control_layer.domain.models.approval import PendingApproval
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.tool import ToolCallRequest
from control_layer.infrastructure.cache.in_memory_cache_repository import (
    InMemoryCacheRepository,
)
from control_layer.infrastructure.repositories.approval_repository import (
    CacheApprovalRepository,
)


def _approval(**overrides: object) -> PendingApproval:
    base: dict[str, object] = {
        "id": "ap_1",
        "identity": Identity(
            sub="anna.kowalska",
            name="Anna Kowalska",
            role="developer",
            location="Krakow, PL",
            region="PL",
            agent_id="agent-anna-dev-7f3a",
        ),
        "tool_call": ToolCallRequest(
            server="github", tool="delete_branch", arguments={"branch": "feature/old-login"}
        ),
        "created_at": datetime(2026, 10, 3, 10, 41, 40, tzinfo=UTC),
        "rule_id": "destructive_requires_approval",
        "status": "pending",
    }
    base.update(overrides)
    return PendingApproval(**base)


async def test_create_then_get_roundtrip() -> None:
    repo = CacheApprovalRepository(InMemoryCacheRepository())
    approval = _approval()

    await repo.create(approval)
    fetched = await repo.get("ap_1")

    assert fetched is not None
    assert fetched.id == "ap_1"
    assert fetched.tool_call.qualified_name == "github.delete_branch"


async def test_get_missing_returns_none() -> None:
    repo = CacheApprovalRepository(InMemoryCacheRepository())

    assert await repo.get("missing") is None


async def test_update_status_persists() -> None:
    repo = CacheApprovalRepository(InMemoryCacheRepository())
    await repo.create(_approval())

    await repo.update_status("ap_1", "approved")

    fetched = await repo.get("ap_1")
    assert fetched.status == "approved"


async def test_update_status_on_missing_is_noop() -> None:
    repo = CacheApprovalRepository(InMemoryCacheRepository())

    await repo.update_status("missing", "approved")


async def test_list_pending_returns_only_pending() -> None:
    repo = CacheApprovalRepository(InMemoryCacheRepository())
    await repo.create(_approval(id="ap_1", status="pending"))
    await repo.create(_approval(id="ap_2", status="approved"))
    await repo.create(_approval(id="ap_3", status="pending"))

    pending = await repo.list_pending()

    assert {a.id for a in pending} == {"ap_1", "ap_3"}
