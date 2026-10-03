from __future__ import annotations

from typing import Protocol

from control_layer.domain.models.approval import PendingApproval
from control_layer.domain.models.enums import ApprovalStatus


class _Cache(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl: float | None = None) -> None: ...
    async def keys(self, prefix: str) -> list[str]: ...


class CacheApprovalRepository:
    _PREFIX = "approval:"

    def __init__(self, cache: _Cache) -> None:
        self._cache = cache

    def _key(self, approval_id: str) -> str:
        return f"{self._PREFIX}{approval_id}"

    async def create(self, approval: PendingApproval) -> None:
        await self._cache.set(self._key(approval.id), approval.model_dump_json())

    async def get(self, approval_id: str) -> PendingApproval | None:
        raw = await self._cache.get(self._key(approval_id))
        if raw is None:
            return None
        return PendingApproval.model_validate_json(raw)

    async def update_status(self, approval_id: str, status: ApprovalStatus) -> None:
        approval = await self.get(approval_id)
        if approval is None:
            return
        approval.status = ApprovalStatus(status)
        await self._cache.set(self._key(approval_id), approval.model_dump_json())

    async def list_pending(self) -> list[PendingApproval]:
        approvals = []
        for key in await self._cache.keys(self._PREFIX):
            raw = await self._cache.get(key)
            if raw is None:
                continue
            approval = PendingApproval.model_validate_json(raw)
            if approval.status == ApprovalStatus.pending:
                approvals.append(approval)
        return approvals
