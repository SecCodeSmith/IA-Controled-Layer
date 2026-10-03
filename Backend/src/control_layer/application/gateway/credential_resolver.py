from __future__ import annotations

import base64
import json
import time

from control_layer.application.use_cases.issue_token import IssueTokenUseCase
from control_layer.domain.exceptions import IdentityRejectedError
from control_layer.domain.ports.user_repository import UserRepository

_JWT_SEGMENTS = 3
_REFRESH_MARGIN_S = 60


def _bearer_value(header: str | None) -> str | None:
    if not header:
        return None
    scheme, _, value = header.partition(" ")
    value = value.strip()
    if scheme.lower() != "bearer" or not value:
        return None
    return value


def peek_subject(token: str) -> str | None:
    parts = token.split(".")
    if len(parts) != _JWT_SEGMENTS:
        return None
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        sub = json.loads(base64.urlsafe_b64decode(payload)).get("sub")
    except (ValueError, AttributeError):
        return None
    return sub if isinstance(sub, str) else None


class GatewayCredentialResolver:
    def __init__(
        self,
        issue_token: IssueTokenUseCase,
        user_repository: UserRepository,
        default_user: str | None,
    ) -> None:
        self._issue_token = issue_token
        self._user_repository = user_repository
        self._default_user = default_user or None
        self._cache: dict[str, tuple[str, float]] = {}

    @property
    def default_user(self) -> str | None:
        return self._default_user

    async def resolve(self, authorization_header: str | None) -> str:
        value = _bearer_value(authorization_header)
        if value is not None and len(value.split(".")) == _JWT_SEGMENTS:
            return value
        if value is not None:
            for user in await self._user_repository.list_all():
                if user.api_key and user.api_key == value:
                    return await self._token_for(user.sub)
        if self._default_user is not None:
            return await self._token_for(self._default_user)
        raise IdentityRejectedError("missing or invalid credentials")

    async def _token_for(self, sub: str) -> str:
        cached = self._cache.get(sub)
        now = time.monotonic()
        if cached is not None and cached[1] > now:
            return cached[0]
        issued = await self._issue_token.execute(sub)
        lifetime = max(issued.expires_in - _REFRESH_MARGIN_S, 0)
        self._cache[sub] = (issued.access_token, now + lifetime)
        return issued.access_token
