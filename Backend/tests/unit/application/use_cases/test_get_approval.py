from __future__ import annotations

import pytest

from control_layer.application.auth.identity_service import IdentityService
from control_layer.application.services.approval_service import ApprovalService
from control_layer.application.use_cases.get_approval import GetApprovalUseCase
from control_layer.domain.exceptions import ApprovalNotFoundError
from control_layer.domain.models.enums import Role
from control_layer.domain.models.identity import TokenClaims
from control_layer.domain.models.tool import ToolCallRequest
from control_layer.domain.models.user import DemoUser


class _FakeTokenVerifier:
    def __init__(self, claims: TokenClaims) -> None:
        self._claims = claims

    async def verify(self, token: str) -> TokenClaims:
        return self._claims

    async def issue(self, claims: TokenClaims) -> str:
        raise NotImplementedError


class _FakeUserRepository:
    def __init__(self, user: DemoUser) -> None:
        self._user = user

    async def list_all(self) -> list[DemoUser]:
        return [self._user]

    async def get(self, sub: str) -> DemoUser | None:
        return self._user if self._user.sub == sub else None


class _FakeApprovalRepository:
    def __init__(self) -> None:
        self._store: dict = {}

    async def create(self, approval) -> None:  # noqa: ANN001
        self._store[approval.id] = approval

    async def get(self, approval_id: str):  # noqa: ANN201
        return self._store.get(approval_id)

    async def update_status(self, approval_id, status) -> None:  # noqa: ANN001
        if approval_id in self._store:
            self._store[approval_id].status = status

    async def list_pending(self):  # noqa: ANN201
        return []


class _FakeCache:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        self._store[key] = value

    async def incr(self, key: str, ttl: int | None = None) -> int:
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def ping(self) -> bool:
        return True

    async def keys(self, prefix: str) -> list[str]:
        return []

    async def flush(self, prefix: str) -> None:
        pass


def _user() -> DemoUser:
    return DemoUser(
        sub="anna.kowalska", name="Anna Kowalska", initials="AK", role=Role.developer,
        location="Krakow, PL", region="PL", agent_id="agent-anna-dev-7f3a", mcp_servers=["github"],
    )


def _claims() -> TokenClaims:
    return TokenClaims(
        sub="anna.kowalska", name="Anna Kowalska", role=Role.developer, location="Krakow, PL",
        region="PL", agent_id="agent-anna-dev-7f3a", iat=1000, exp=29800,
    )


async def test_execute_resolves_token_and_returns_approval() -> None:
    identity_service = IdentityService(_FakeTokenVerifier(_claims()), _FakeUserRepository(_user()))
    approval_repo = _FakeApprovalRepository()
    approval_service = ApprovalService(approval_repo, _FakeCache())
    use_case = GetApprovalUseCase(approval_service, identity_service)

    identity = await identity_service.resolve("token", session_id="s1")
    created = await approval_service.create(
        identity, ToolCallRequest(server="github", tool="delete_branch", arguments={}), "rule", "reason"
    )

    result = await use_case.execute("token", created.id)
    assert result.id == created.id


async def test_execute_raises_for_unknown_approval() -> None:
    identity_service = IdentityService(_FakeTokenVerifier(_claims()), _FakeUserRepository(_user()))
    approval_service = ApprovalService(_FakeApprovalRepository(), _FakeCache())
    use_case = GetApprovalUseCase(approval_service, identity_service)
    with pytest.raises(ApprovalNotFoundError):
        await use_case.execute("token", "ap_doesnotexist")
