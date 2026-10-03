from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Header, Request

from control_layer.domain.exceptions import IdentityRejectedError

if TYPE_CHECKING:
    from control_layer.presentation.composition_root import Container


def get_container(request: Request) -> "Container":
    return request.app.state.container


def require_admin(
    request: Request,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    container: Container = request.app.state.container
    expected = container.settings.admin_token
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
