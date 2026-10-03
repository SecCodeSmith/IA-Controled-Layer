from __future__ import annotations

from typing import Protocol

from control_layer.domain.models.identity import TokenClaims


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> TokenClaims: ...

    async def issue(self, claims: TokenClaims) -> str: ...
