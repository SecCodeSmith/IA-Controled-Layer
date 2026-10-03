from __future__ import annotations

import re
from typing import Annotated

from fastapi import Depends, Header, Request

from control_layer.application.gateway.credential_resolver import peek_subject
from control_layer.domain.exceptions import IdentityRejectedError
from control_layer.presentation.composition_root import Container


def get_container(request: Request) -> Container:
    return request.app.state.container


ContainerDep = Annotated[Container, Depends(get_container)]


def require_admin(
    request: Request,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    expected = request.app.state.container.settings.admin_token
    token = x_admin_token or request.query_params.get("admin_token")
    if not token or token != expected:
        raise IdentityRejectedError("missing or invalid admin token")


def bearer_token(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise IdentityRejectedError("missing or malformed Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise IdentityRejectedError("missing bearer token")
    return token


def session_id(
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
) -> str | None:
    return x_session_id


async def gateway_token(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> str:
    return await request.app.state.container.gateway_credentials.resolve(authorization)


_CLIENT_MAX_CHARS = 24


def client_label(user_agent: str | None) -> str:
    match = re.match(r"[A-Za-z0-9]+", user_agent or "")
    return match.group(0)[:_CLIENT_MAX_CHARS] if match else "unknown"


def gateway_session_id(token: str, x_session_id: str | None, user_agent: str | None) -> str:
    if x_session_id:
        return x_session_id
    return f"gateway-{peek_subject(token) or 'unknown'}-{client_label(user_agent)}"


def gateway_session(
    token: Annotated[str, Depends(gateway_token)],
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    user_agent: str | None = Header(default=None, alias="User-Agent"),
) -> str:
    return gateway_session_id(token, x_session_id, user_agent)


GatewayTokenDep = Annotated[str, Depends(gateway_token)]
GatewaySessionDep = Annotated[str, Depends(gateway_session)]
BearerDep = Annotated[str, Depends(bearer_token)]
SessionDep = Annotated[str | None, Depends(session_id)]
AdminDeps = [Depends(require_admin)]
