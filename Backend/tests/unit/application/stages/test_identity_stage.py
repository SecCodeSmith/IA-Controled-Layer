from __future__ import annotations

import pytest

from control_layer.application.pipeline.stages.identity import IdentityStage
from control_layer.domain.exceptions import IdentityRejectedError
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.enums import CallStatus, InterceptionPoint, Role, StageName
from control_layer.domain.models.identity import TokenClaims
from control_layer.domain.models.user import DemoUser
from control_layer.domain.policy.parser import parse_policy_document


class _FakeTokenVerifier:
    def __init__(self, claims=None, error=None):  # noqa: ANN001
        self._claims = claims
        self._error = error

    async def verify(self, token: str) -> TokenClaims:
        if self._error is not None:
            raise self._error
        return self._claims

    async def issue(self, claims: TokenClaims) -> str:
        raise NotImplementedError


class _FakeUserRepository:
    def __init__(self, users):  # noqa: ANN001
        self._users = users

    async def list_all(self):
        return list(self._users.values())

    async def get(self, sub: str):
        return self._users.get(sub)


def _claims() -> TokenClaims:
    return TokenClaims(
        sub="anna.kowalska",
        name="Anna Kowalska",
        role=Role.developer,
        location="Krakow, PL",
        region="PL",
        agent_id="agent-anna-dev-7f3a",
        iat=1000,
        exp=29800,
    )


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


def _policy():
    data = {
        "version": 1,
        "profile": "balanced",
        "models": {"allowed": ["mock"], "pricing": {}},
        "roles": {},
        "locations": {},
        "rules": [],
        "budgets": {
            "per_user_tokens": 1000,
            "per_user_cost_usd": 1.0,
            "max_tokens_per_request": 100,
            "upstream_timeout_s": 30,
            "warn_at_percent": 80,
            "on_exceeded": "block",
        },
    }
    return parse_policy_document(data, source_hash="h")


def _ctx(token: str | None) -> ProcessingContext:
    return ProcessingContext(
        identity=None,
        point=InterceptionPoint.prompt,
        text="hi",
        session_id="s1",
        call_id="c1",
        metadata={"token": token},
    )


async def test_process_sets_identity_and_allows() -> None:
    stage = IdentityStage(
        _FakeTokenVerifier(claims=_claims()), _FakeUserRepository({"anna.kowalska": _user()})
    )
    ctx = _ctx("sometoken")
    result = await stage.process(ctx, _policy())
    assert result.action.value == "allow"
    assert ctx.identity is not None
    assert ctx.identity.sub == "anna.kowalska"
    assert ctx.identity.session_id == "s1"


async def test_process_raises_identity_rejected_on_bad_token() -> None:
    stage = IdentityStage(
        _FakeTokenVerifier(error=IdentityRejectedError("signature mismatch")),
        _FakeUserRepository({}),
    )
    with pytest.raises(IdentityRejectedError):
        await stage.process(_ctx("badtoken"), _policy())


async def test_process_raises_identity_rejected_on_missing_token() -> None:
    stage = IdentityStage(_FakeTokenVerifier(claims=_claims()), _FakeUserRepository({}))
    with pytest.raises(IdentityRejectedError):
        await stage.process(_ctx(None), _policy())


def test_stage_name_is_identity() -> None:
    stage = IdentityStage(_FakeTokenVerifier(claims=_claims()), _FakeUserRepository({}))
    assert stage.name == StageName.identity


async def test_result_status_maps_to_allowed() -> None:
    from control_layer.domain.models.decision import status_for

    stage = IdentityStage(
        _FakeTokenVerifier(claims=_claims()), _FakeUserRepository({"anna.kowalska": _user()})
    )
    result = await stage.process(_ctx("sometoken"), _policy())
    assert status_for(result.action) == CallStatus.ALLOWED
