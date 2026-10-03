from __future__ import annotations

import base64
import json

import pytest

from control_layer.application.gateway.credential_resolver import (
    GatewayCredentialResolver,
    peek_subject,
)
from control_layer.application.use_cases.issue_token import IssueTokenUseCase
from control_layer.domain.exceptions import IdentityRejectedError
from control_layer.domain.models.enums import Role
from control_layer.domain.models.identity import TokenClaims
from control_layer.domain.models.user import DemoUser


def _user(sub: str, api_key: str | None) -> DemoUser:
    return DemoUser(
        sub=sub,
        name=sub,
        initials="XX",
        role=Role.developer,
        location="Krakow, PL",
        region="PL",
        agent_id=f"agent-{sub}",
        api_key=api_key,
    )


class _Users:
    def __init__(self) -> None:
        self._users = {
            "anna": _user("anna", "ck-anna"),
            "marek": _user("marek", "ck-marek"),
            "nokey": _user("nokey", None),
        }

    async def list_all(self) -> list[DemoUser]:
        return list(self._users.values())

    async def get(self, sub: str) -> DemoUser | None:
        return self._users.get(sub)


def _b64(sub: str) -> str:
    raw = json.dumps({"sub": sub}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


class _Verifier:
    def __init__(self) -> None:
        self.issued: list[TokenClaims] = []

    async def verify(self, token: str) -> TokenClaims:
        raise NotImplementedError

    async def issue(self, claims: TokenClaims) -> str:
        self.issued.append(claims)
        return f"h.{_b64(claims.sub)}.s"


def _resolver(default_user: str | None) -> tuple[GatewayCredentialResolver, _Verifier]:
    users = _Users()
    verifier = _Verifier()
    issue = IssueTokenUseCase(users, verifier)
    return GatewayCredentialResolver(issue, users, default_user), verifier


async def test_jwt_passes_through_unchanged() -> None:
    resolver, verifier = _resolver(None)
    assert await resolver.resolve("Bearer aaa.bbb.ccc") == "aaa.bbb.ccc"
    assert verifier.issued == []


async def test_api_key_resolves_to_its_user() -> None:
    resolver, _ = _resolver("anna")
    token = await resolver.resolve("Bearer ck-marek")
    assert peek_subject(token) == "marek"


async def test_api_key_token_is_cached() -> None:
    resolver, verifier = _resolver(None)
    first = await resolver.resolve("Bearer ck-anna")
    second = await resolver.resolve("Bearer ck-anna")
    assert first == second
    assert len(verifier.issued) == 1


@pytest.mark.parametrize("header", [None, "", "Bearer", "Basic abc", "Bearer unknown-key"])
async def test_falls_back_to_default_user(header: str | None) -> None:
    resolver, _ = _resolver("anna")
    assert peek_subject(await resolver.resolve(header)) == "anna"


@pytest.mark.parametrize("header", [None, "Bearer unknown-key", "Bearer"])
async def test_rejects_when_default_user_disabled(header: str | None) -> None:
    resolver, _ = _resolver(None)
    with pytest.raises(IdentityRejectedError):
        await resolver.resolve(header)


async def test_empty_default_user_means_disabled() -> None:
    resolver, _ = _resolver("")
    with pytest.raises(IdentityRejectedError):
        await resolver.resolve(None)


def test_peek_subject_handles_garbage() -> None:
    assert peek_subject("not-a-jwt") is None
    assert peek_subject("a.!!!.c") is None
