from __future__ import annotations

from typing import Protocol

from control_layer.domain.models.approval import PendingApproval
from control_layer.domain.models.enums import ApprovalStatus


class ApprovalRepository(Protocol):
    async def create(self, approval: PendingApproval) -> None: ...

    async def get(self, approval_id: str) -> PendingApproval | None: ...

    async def update_status(self, approval_id: str, status: ApprovalStatus) -> None: ...

    async def list_pending(self) -> list[PendingApproval]: ...
