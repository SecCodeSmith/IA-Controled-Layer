from __future__ import annotations

from control_layer.application.auth.identity_service import IdentityService
from control_layer.application.services.approval_service import ApprovalService
from control_layer.domain.models.approval import PendingApproval


class GetApprovalUseCase:
    def __init__(self, approval_service: ApprovalService, identity_service: IdentityService) -> None:
        self._approval_service = approval_service
        self._identity_service = identity_service

    async def execute(self, token: str, approval_id: str) -> PendingApproval:
        identity = await self._identity_service.resolve(token, session_id="")
        return await self._approval_service.get_for(identity, approval_id)
