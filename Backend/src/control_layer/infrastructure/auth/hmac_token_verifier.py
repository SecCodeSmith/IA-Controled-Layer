from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Callable

from pydantic import ValidationError

from control_layer.domain.exceptions import IdentityRejectedError
from control_layer.domain.models.identity import TokenClaims

_DEFAULT_ISSUER = "control-layer-mock-sso"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


class HmacTokenVerifier:
    def __init__(
        self,
        secret: str,
        issuer: str = _DEFAULT_ISSUER,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._secret = secret.encode("utf-8")
        self._issuer = issuer
        self._clock = clock

    def _sign(self, signing_input: bytes) -> bytes:
        return hmac.new(self._secret, signing_input, hashlib.sha256).digest()

    async def issue(self, claims: TokenClaims) -> str:
        payload = claims.model_dump(mode="json")

        header = {"alg": "HS256", "typ": "JWT"}
        header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
        payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        signature_b64 = _b64url_encode(self._sign(signing_input))
        return f"{header_b64}.{payload_b64}.{signature_b64}"

    async def verify(self, token: str) -> TokenClaims:
        parts = token.split(".")
        if len(parts) != 3:
            raise IdentityRejectedError("malformed token")
        header_b64, payload_b64, signature_b64 = parts

        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected_signature = self._sign(signing_input)
        try:
            actual_signature = _b64url_decode(signature_b64)
        except (ValueError, TypeError) as exc:
            raise IdentityRejectedError("invalid token encoding") from exc

        if not hmac.compare_digest(expected_signature, actual_signature):
            raise IdentityRejectedError("signature mismatch")

        try:
            payload = json.loads(_b64url_decode(payload_b64))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise IdentityRejectedError("malformed payload") from exc

        if payload.get("iss") != self._issuer:
            raise IdentityRejectedError("wrong issuer")

        exp = payload.get("exp")
        if exp is None or exp < self._clock():
            raise IdentityRejectedError("expired token")

        try:
            return TokenClaims(**payload)
        except ValidationError as exc:
            raise IdentityRejectedError(f"malformed claims: {exc}") from exc
