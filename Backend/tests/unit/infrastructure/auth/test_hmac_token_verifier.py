from __future__ import annotations

import base64
import json

import pytest

from control_layer.domain.exceptions import IdentityRejectedError
from control_layer.domain.models.identity import TokenClaims
from control_layer.infrastructure.auth.hmac_token_verifier import HmacTokenVerifier


def _claims(iat: int, exp: int, **overrides: object) -> TokenClaims:
    data: dict[str, object] = {
        "sub": "anna.kowalska",
        "name": "Anna Kowalska",
        "role": "developer",
        "location": "Krakow, PL",
        "region": "PL",
        "agent_id": "agent-anna-dev-7f3a",
        "iat": iat,
        "exp": exp,
    }
    data.update(overrides)
    return TokenClaims(**data)


def _clock(value: list[float]):
    def _now() -> float:
        return value[0]

    return _now


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


async def test_issue_then_verify_roundtrip() -> None:
    clock = _clock([1_000_000.0])
    verifier = HmacTokenVerifier(secret="test-secret", clock=clock)
    claims = _claims(iat=1_000_000, exp=1_003_600)

    token = await verifier.issue(claims)
    result = await verifier.verify(token)

    assert result == claims
    assert result.sub == "anna.kowalska"
    assert result.role == "developer"
    assert result.iss == "control-layer-mock-sso"


async def test_tampered_payload_rejected() -> None:
    verifier = HmacTokenVerifier(secret="test-secret")
    claims = _claims(iat=1_000_000, exp=1_003_600)
    token = await verifier.issue(claims)

    header_b64, payload_b64, signature_b64 = token.split(".")
    payload = json.loads(_b64url_decode(payload_b64))
    payload["role"] = "finance"
    tampered_payload_b64 = _b64url_encode(json.dumps(payload).encode())
    tampered_token = f"{header_b64}.{tampered_payload_b64}.{signature_b64}"

    with pytest.raises(IdentityRejectedError):
        await verifier.verify(tampered_token)


async def test_bad_signature_rejected() -> None:
    verifier = HmacTokenVerifier(secret="test-secret")
    claims = _claims(iat=1_000_000, exp=1_003_600)
    token = await verifier.issue(claims)
    header_b64, payload_b64, _ = token.split(".")
    bogus_signature = _b64url_encode(b"not-a-real-signature-00")
    tampered_token = f"{header_b64}.{payload_b64}.{bogus_signature}"

    with pytest.raises(IdentityRejectedError):
        await verifier.verify(tampered_token)


async def test_wrong_secret_rejected() -> None:
    issuing_verifier = HmacTokenVerifier(secret="secret-a")
    claims = _claims(iat=1_000_000, exp=1_003_600)
    token = await issuing_verifier.issue(claims)

    verifier = HmacTokenVerifier(secret="secret-b")

    with pytest.raises(IdentityRejectedError):
        await verifier.verify(token)


async def test_expired_token_rejected() -> None:
    issuing_clock = _clock([1_000_000.0])
    verifier = HmacTokenVerifier(secret="test-secret", clock=issuing_clock)
    claims = _claims(iat=1_000_000, exp=1_000_010)
    token = await verifier.issue(claims)

    expired_clock = _clock([1_000_011.0])
    expired_verifier = HmacTokenVerifier(secret="test-secret", clock=expired_clock)

    with pytest.raises(IdentityRejectedError):
        await expired_verifier.verify(token)


async def test_wrong_issuer_rejected() -> None:
    verifier = HmacTokenVerifier(secret="test-secret", issuer="some-other-issuer")
    claims = _claims(iat=1_000_000, exp=1_003_600, iss="some-other-issuer")
    token = await verifier.issue(claims)

    expected_issuer_verifier = HmacTokenVerifier(
        secret="test-secret", issuer="control-layer-mock-sso"
    )

    with pytest.raises(IdentityRejectedError):
        await expected_issuer_verifier.verify(token)


async def test_malformed_token_rejected() -> None:
    verifier = HmacTokenVerifier(secret="test-secret")

    with pytest.raises(IdentityRejectedError):
        await verifier.verify("not-a-valid-jwt")
