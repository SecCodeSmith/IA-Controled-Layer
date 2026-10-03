from __future__ import annotations

import time

from control_layer.application.use_cases.outcomes import TokenIssued
from control_layer.domain.exceptions import IdentityRejectedError
from control_layer.domain.models.identity import TokenClaims
from control_layer.domain.ports.token_verifier import TokenVerifier
from control_layer.domain.ports.user_repository import UserRepository

_DEFAULT_TTL_S = 28800


class IssueTokenUseCase:
    def __init__(
        self,
        user_repository: UserRepository,
        token_verifier: TokenVerifier,
        ttl_s: int = _DEFAULT_TTL_S,
    ) -> None:
        self._user_repository = user_repository
        self._token_verifier = token_verifier
        self._ttl_s = ttl_s

    async def execute(self, sub: str) -> TokenIssued:
        user = await self._user_repository.get(sub)
        if user is None:
            raise IdentityRejectedError(f"unknown user: {sub}")

        now = int(time.time())
        claims = TokenClaims(
            sub=user.sub,
            name=user.name,
            role=user.role,
            location=user.location,
            region=user.region,
            agent_id=user.agent_id,
            iat=now,
            exp=now + self._ttl_s,
        )
        access_token = await self._token_verifier.issue(claims)
        return TokenIssued(access_token=access_token, expires_in=self._ttl_s, claims=claims)
