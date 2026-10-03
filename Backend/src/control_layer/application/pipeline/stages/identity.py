from __future__ import annotations

from control_layer.application.auth.identity_service import IdentityService
from control_layer.application.pipeline.stage_base import BaseStage
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import StageResult
from control_layer.domain.models.enums import StageName
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.ports.token_verifier import TokenVerifier
from control_layer.domain.ports.user_repository import UserRepository


class IdentityStage(BaseStage):
    def __init__(self, token_verifier: TokenVerifier, user_repository: UserRepository) -> None:
        super().__init__(StageName.identity)
        self._identity_service = IdentityService(token_verifier, user_repository)

    async def process(self, ctx: ProcessingContext, policy: PolicyDocument) -> StageResult:
        token = ctx.metadata.get("token")
        identity = await self._identity_service.resolve(token, ctx.session_id)
        ctx.identity = identity
        return self.allow(0.0)
