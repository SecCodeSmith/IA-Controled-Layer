from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from control_layer.application.services.approval_service import ApprovalService
from control_layer.domain.exceptions import ApprovalNotFoundError
from control_layer.domain.models.enums import ApprovalStatus, Role
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.tool import ToolCallRequest


class _FakeApprovalRepository:
    def __init__(self) -> None:
        self._store: dict = {}

    async def create(self, approval) -> None:  # noqa: ANN001
        self._store[approval.id] = approval

    async def get(self, approval_id: str):  # noqa: ANN201
        return self._store.get(approval_id)

    async def update_status(self, approval_id: str, status: ApprovalStatus) -> None:
        if approval_id in self._store:
            self._store[approval_id].status = status

    async def list_pending(self):  # noqa: ANN201
        return [a for a in self._store.values() if a.status == ApprovalStatus.pending]


class _FakeCache:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        self._store[key] = value

    async def incr(self, key: str, ttl: int | None = None) -> int:
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def ping(self) -> bool:
        return True

    async def keys(self, prefix: str) -> list[str]:
        return [k for k in self._store if k.startswith(prefix)]

    async def flush(self, prefix: str) -> None:
        for k in list(self._store):
            if k.startswith(prefix):
                del self._store[k]

    def expire(self, key: str) -> None:
        self._store.pop(key, None)


def _identity(sub: str = "anna.kowalska") -> Identity:
    return Identity(
        sub=sub,
        name="Anna Kowalska",
        role=Role.developer,
        location="Krakow, PL",
        region="PL",
        agent_id="agent-anna-dev-7f3a",
    )


def _tool_call() -> ToolCallRequest:
    return ToolCallRequest(server="github", tool="delete_branch", arguments={"branch": "old"})


async def test_create_assigns_ap_prefixed_id_with_12_hex_chars() -> None:
    service = ApprovalService(_FakeApprovalRepository(), _FakeCache())
    approval = await service.create(_identity(), _tool_call(), "destructive_requires_approval", "reason")
    assert approval.id.startswith("ap_")
    assert len(approval.id) == len("ap_") + 12


async def test_create_sets_expiry_15_minutes_out() -> None:
    now = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
    service = ApprovalService(_FakeApprovalRepository(), _FakeCache(), clock=lambda: now)
    approval = await service.create(_identity(), _tool_call(), "rule", "reason")
    assert approval.expires_at == now + timedelta(minutes=15)


async def test_get_for_returns_approval_for_owning_user() -> None:
    service = ApprovalService(_FakeApprovalRepository(), _FakeCache())
    created = await service.create(_identity(), _tool_call(), "rule", "reason")
    fetched = await service.get_for(_identity(), created.id)
    assert fetched.id == created.id


async def test_get_for_raises_for_unknown_approval() -> None:
    service = ApprovalService(_FakeApprovalRepository(), _FakeCache())
    with pytest.raises(ApprovalNotFoundError):
        await service.get_for(_identity(), "ap_doesnotexist")


async def test_get_for_raises_when_belongs_to_another_user() -> None:
    service = ApprovalService(_FakeApprovalRepository(), _FakeCache())
    created = await service.create(_identity("anna.kowalska"), _tool_call(), "rule", "reason")
    with pytest.raises(ApprovalNotFoundError):
        await service.get_for(_identity("marek.nowak"), created.id)


async def test_get_for_raises_and_marks_expired_when_cache_marker_gone() -> None:
    cache = _FakeCache()
    repo = _FakeApprovalRepository()
    service = ApprovalService(repo, cache)
    created = await service.create(_identity(), _tool_call(), "rule", "reason")
    cache.expire(f"approval_alive:{created.id}")

    with pytest.raises(ApprovalNotFoundError):
        await service.get_for(_identity(), created.id)

    stored = await repo.get(created.id)
    assert stored.status == ApprovalStatus.expired


async def test_mark_updates_status_via_repository() -> None:
    repo = _FakeApprovalRepository()
    service = ApprovalService(repo, _FakeCache())
    created = await service.create(_identity(), _tool_call(), "rule", "reason")
    await service.mark(created.id, ApprovalStatus.executed)
    stored = await repo.get(created.id)
    assert stored.status == ApprovalStatus.executed
