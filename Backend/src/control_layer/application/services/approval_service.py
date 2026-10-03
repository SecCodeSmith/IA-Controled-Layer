from __future__ import annotations

import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from control_layer.domain.exceptions import ApprovalNotFoundError
from control_layer.domain.models.approval import PendingApproval
from control_layer.domain.models.enums import ApprovalStatus
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.tool import ToolCallRequest
from control_layer.domain.ports.approval_repository import ApprovalRepository
from control_layer.domain.ports.cache_repository import CacheRepository

_EXPIRY_S = 15 * 60
_ALIVE_PREFIX = "approval_alive:"


class ApprovalService:
    def __init__(
        self,
        approval_repository: ApprovalRepository,
        cache: CacheRepository,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._approval_repository = approval_repository
        self._cache = cache
        self._clock = clock

    async def create(
        self, identity: Identity, tool_call: ToolCallRequest, rule_id: str, reason: str
    ) -> PendingApproval:
        approval_id = "ap_" + secrets.token_hex(6)
        now = self._clock()
        approval = PendingApproval(
            id=approval_id,
            identity=identity,
            tool_call=tool_call,
            created_at=now,
            rule_id=rule_id,
            status=ApprovalStatus.pending,
            expires_at=now + timedelta(seconds=_EXPIRY_S),
            reason=reason,
        )
        await self._approval_repository.create(approval)
        await self._cache.set(self._alive_key(approval_id), "1", ttl=_EXPIRY_S)
        return approval

    async def get_for(self, identity: Identity, approval_id: str) -> PendingApproval:
        approval = await self._approval_repository.get(approval_id)
        if approval is None or approval.identity.sub != identity.sub:
            raise ApprovalNotFoundError(approval_id)

        alive = await self._cache.get(self._alive_key(approval_id))
        if alive is None:
            if approval.status == ApprovalStatus.pending:
                await self._approval_repository.update_status(approval_id, ApprovalStatus.expired)
            raise ApprovalNotFoundError(approval_id)

        return approval

    async def mark(self, approval_id: str, status: ApprovalStatus) -> None:
        await self._approval_repository.update_status(approval_id, status)

    @staticmethod
    def _alive_key(approval_id: str) -> str:
        return f"{_ALIVE_PREFIX}{approval_id}"
