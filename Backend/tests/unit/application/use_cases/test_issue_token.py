from __future__ import annotations

import pytest

from control_layer.application.use_cases.issue_token import IssueTokenUseCase
from control_layer.domain.exceptions import IdentityRejectedError
from control_layer.domain.models.enums import Role
from control_layer.domain.models.identity import TokenClaims
from control_layer.domain.models.user import DemoUser


class _FakeUserRepository:
    def __init__(self, users: dict[str, DemoUser]) -> None:
        self._users = users

    async def list_all(self) -> list[DemoUser]:
        return list(self._users.values())

    async def get(self, sub: str) -> DemoUser | None:
        return self._users.get(sub)


class _FakeTokenVerifier:
    def __init__(self) -> None:
        self.issued: list[TokenClaims] = []

    async def verify(self, token: str) -> TokenClaims:
        raise NotImplementedError

    async def issue(self, claims: TokenClaims) -> str:
        self.issued.append(claims)
        return f"token-for-{claims.sub}"


def _user() -> DemoUser:
    return DemoUser(
        sub="anna.kowalska",
        name="Anna Kowalska",
        initials="AK",
        role=Role.developer,
        location="Krakow, PL",
        region="PL",
        agent_id="agent-anna-dev-7f3a",
        mcp_servers=["github"],
    )


async def test_issues_token_with_claims_from_user_record() -> None:
    verifier = _FakeTokenVerifier()
    use_case = IssueTokenUseCase(_FakeUserRepository({"anna.kowalska": _user()}), verifier)
    result = await use_case.execute("anna.kowalska")
    assert result.access_token == "token-for-anna.kowalska"
    assert result.token_type == "Bearer"
    assert result.expires_in == 28800
    assert result.claims.sub == "anna.kowalska"
    assert result.claims.role == Role.developer


async def test_respects_custom_ttl() -> None:
    use_case = IssueTokenUseCase(
        _FakeUserRepository({"anna.kowalska": _user()}), _FakeTokenVerifier(), ttl_s=60
    )
    result = await use_case.execute("anna.kowalska")
    assert result.expires_in == 60
    assert result.claims.exp - result.claims.iat == 60


async def test_raises_for_unknown_sub() -> None:
    use_case = IssueTokenUseCase(_FakeUserRepository({}), _FakeTokenVerifier())
    with pytest.raises(IdentityRejectedError):
        await use_case.execute("ghost")
