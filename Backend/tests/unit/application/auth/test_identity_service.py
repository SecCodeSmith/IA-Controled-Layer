from __future__ import annotations

import pytest

from control_layer.application.auth.identity_service import IdentityService
from control_layer.domain.exceptions import IdentityRejectedError
from control_layer.domain.models.enums import Role
from control_layer.domain.models.identity import TokenClaims
from control_layer.domain.models.user import DemoUser


class _FakeTokenVerifier:
    def __init__(self, claims: TokenClaims | None = None, error: Exception | None = None) -> None:
        self._claims = claims
        self._error = error

    async def verify(self, token: str) -> TokenClaims:
        if self._error is not None:
            raise self._error
        assert self._claims is not None
        return self._claims

    async def issue(self, claims: TokenClaims) -> str:
        raise NotImplementedError


class _FakeUserRepository:
    def __init__(self, users: dict[str, DemoUser]) -> None:
        self._users = users

    async def list_all(self) -> list[DemoUser]:
        return list(self._users.values())

    async def get(self, sub: str) -> DemoUser | None:
        return self._users.get(sub)


def _claims(sub: str = "anna.kowalska") -> TokenClaims:
    return TokenClaims(
        sub=sub,
        name="Anna Kowalska",
        role=Role.developer,
        location="Krakow, PL",
        region="PL",
        agent_id="agent-anna-dev-7f3a",
        iat=1000,
        exp=29800,
    )


def _user(sub: str = "anna.kowalska", role: Role = Role.developer) -> DemoUser:
    return DemoUser(
        sub=sub,
        name="Anna Kowalska",
        initials="AK",
        role=role,
        location="Krakow, PL",
        region="PL",
        agent_id="agent-anna-dev-7f3a",
        mcp_servers=["github", "ci"],
    )


async def test_resolve_builds_identity_from_authoritative_user_record() -> None:
    service = IdentityService(
        _FakeTokenVerifier(claims=_claims()),
        _FakeUserRepository({"anna.kowalska": _user()}),
    )
    identity = await service.resolve("sometoken", session_id="s-1")
    assert identity.sub == "anna.kowalska"
    assert identity.role == Role.developer
    assert identity.session_id == "s-1"


async def test_resolve_propagates_token_verifier_rejection() -> None:
    service = IdentityService(
        _FakeTokenVerifier(error=IdentityRejectedError("signature mismatch")),
        _FakeUserRepository({}),
    )
    with pytest.raises(IdentityRejectedError):
        await service.resolve("badtoken", session_id="s-1")


async def test_resolve_rejects_when_user_no_longer_exists() -> None:
    service = IdentityService(
        _FakeTokenVerifier(claims=_claims(sub="ghost.user")),
        _FakeUserRepository({}),
    )
    with pytest.raises(IdentityRejectedError):
        await service.resolve("sometoken", session_id="s-1")


async def test_resolve_rejects_missing_token() -> None:
    service = IdentityService(_FakeTokenVerifier(claims=_claims()), _FakeUserRepository({}))
    with pytest.raises(IdentityRejectedError):
        await service.resolve("", session_id="s-1")


async def test_resolve_uses_authoritative_role_even_if_claims_differ() -> None:
    claims = _claims(sub="anna.kowalska")
    service = IdentityService(
        _FakeTokenVerifier(claims=claims),
        _FakeUserRepository({"anna.kowalska": _user(role=Role.finance)}),
    )
    identity = await service.resolve("sometoken", session_id="s-1")
    assert identity.role == Role.finance
