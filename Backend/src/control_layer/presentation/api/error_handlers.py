from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from control_layer.domain import exceptions as exc_module
from control_layer.domain.models.enums import CallStatus, StageName


def error_response(
    status_code: int,
    code: str,
    status: CallStatus,
    reason: str,
    *,
    stage: StageName | None = None,
    rule_id: str | None = None,
    owasp: list[str] | None = None,
    call_id: str | None = None,
) -> JSONResponse:
    content: dict[str, Any] = {
        "error": {
            "code": code,
            "status": status.value,
            "stage": stage.value if stage is not None else None,
            "rule_id": rule_id,
            "reason": reason,
            "owasp": owasp or [],
            "call_id": call_id,
        }
    }
    return JSONResponse(status_code=status_code, content=content)


async def _handle_identity_rejected(
    request: Request, exc: exc_module.IdentityRejectedError
) -> JSONResponse:
    return error_response(
        401,
        "identity_rejected",
        CallStatus.BLOCKED,
        exc.reason,
        stage=StageName.identity,
        call_id=getattr(exc, "call_id", None),
    )


async def _handle_policy_violation(
    request: Request, exc: exc_module.PolicyViolationError
) -> JSONResponse:
    violation = exc.violation
    return error_response(
        403,
        "policy_violation",
        exc.status,
        violation.reason or f"blocked by rule {violation.rule_id}",
        stage=violation.stage,
        rule_id=violation.rule_id,
        owasp=violation.owasp,
        call_id=getattr(exc, "call_id", None),
    )


async def _handle_quarantined(
    request: Request, exc: exc_module.QuarantinedError
) -> JSONResponse:
    return error_response(
        403,
        "quarantined",
        CallStatus.BLOCKED,
        exc.reason,
        stage=StageName.behavior,
        rule_id="circuit_breaker",
        call_id=getattr(exc, "call_id", None),
    )


async def _handle_rate_limited(
    request: Request, exc: exc_module.RateLimitedError
) -> JSONResponse:
    return error_response(
        429,
        "rate_limited",
        CallStatus.BLOCKED,
        exc.reason,
        stage=StageName.behavior,
        rule_id="rate_limit",
        call_id=getattr(exc, "call_id", None),
    )


async def _handle_budget_exceeded(
    request: Request, exc: exc_module.BudgetExceededError
) -> JSONResponse:
    return error_response(
        403,
        "budget_exceeded",
        CallStatus.BLOCKED,
        exc.reason,
        stage=StageName.resource,
        call_id=getattr(exc, "call_id", None),
    )


async def _handle_upstream_error(
    request: Request, exc: exc_module.UpstreamProviderError
) -> JSONResponse:
    return error_response(
        502,
        "upstream_error",
        CallStatus.BLOCKED,
        exc.reason,
        call_id=getattr(exc, "call_id", None),
    )


async def _handle_policy_validation(
    request: Request, exc: exc_module.PolicyValidationError
) -> JSONResponse:
    return error_response(
        422,
        "validation_error",
        CallStatus.BLOCKED,
        exc.reason,
        call_id=getattr(exc, "call_id", None),
    )


async def _handle_request_validation(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return error_response(422, "validation_error", CallStatus.BLOCKED, str(exc))


async def _handle_not_found(request: Request, exc: Exception) -> JSONResponse:
    reason = str(exc) or exc.__class__.__name__
    return error_response(
        404,
        "not_found",
        CallStatus.BLOCKED,
        reason,
        call_id=getattr(exc, "call_id", None),
    )


_STATIC_HANDLERS: tuple[tuple[str, Any], ...] = (
    ("IdentityRejectedError", _handle_identity_rejected),
    ("PolicyViolationError", _handle_policy_violation),
    ("QuarantinedError", _handle_quarantined),
    ("RateLimitedError", _handle_rate_limited),
    ("BudgetExceededError", _handle_budget_exceeded),
    ("UpstreamProviderError", _handle_upstream_error),
    ("PolicyValidationError", _handle_policy_validation),
)

_NOT_FOUND_CLASS_NAMES: tuple[str, ...] = (
    "ApprovalNotFoundError",
    "CallNotFoundError",
    "UnknownToolError",
)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _handle_request_validation)

    for class_name, handler in _STATIC_HANDLERS:
        exc_class = getattr(exc_module, class_name, None)
        if exc_class is not None:
            app.add_exception_handler(exc_class, handler)

    for class_name in _NOT_FOUND_CLASS_NAMES:
        exc_class = getattr(exc_module, class_name, None)
        if exc_class is not None:
            app.add_exception_handler(exc_class, _handle_not_found)
