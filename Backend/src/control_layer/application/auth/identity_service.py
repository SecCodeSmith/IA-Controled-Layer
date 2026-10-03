from __future__ import annotations

from control_layer.domain.exceptions import IdentityRejectedError
from control_layer.domain.models.identity import Identity
from control_layer.domain.ports.token_verifier import TokenVerifier
from control_layer.domain.ports.user_repository import UserRepository


class IdentityService:
    def __init__(self, token_verifier: TokenVerifier, user_repository: UserRepository) -> None:
        self._token_verifier = token_verifier
        self._user_repository = user_repository

    async def resolve(self, token: str | None, session_id: str) -> Identity:
        if not token:
            raise IdentityRejectedError("missing bearer token")

        claims = await self._token_verifier.verify(token)

        user = await self._user_repository.get(claims.sub)
        if user is None:
            raise IdentityRejectedError(f"unknown user: {claims.sub}")

        return Identity(
            sub=user.sub,
            name=user.name,
            role=user.role,
            location=user.location,
            region=user.region,
            agent_id=user.agent_id,
            session_id=session_id,
        )
