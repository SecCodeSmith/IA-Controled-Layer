from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from control_layer.application.selftest.attack_run_manager import RunNotFoundError
from control_layer.application.use_cases.admin.exports import ExportNotAvailableError
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


@dataclass(frozen=True)
class ErrorFields:
    http_status: int
    code: str
    status: CallStatus
    reason: str
    stage: StageName | None = None
    rule_id: str | None = None
    owasp: list[str] = field(default_factory=list)
    call_id: str | None = None


def describe_error(exc: Exception) -> ErrorFields | None:
    call_id = getattr(exc, "call_id", None)
    if isinstance(exc, exc_module.IdentityRejectedError):
        return ErrorFields(401, "identity_rejected", CallStatus.BLOCKED, exc.reason,
                           StageName.identity, call_id=call_id)
    if isinstance(exc, exc_module.PolicyViolationError):
        violation = exc.violation
        return ErrorFields(
            403, "policy_violation", exc.status,
            violation.reason or f"blocked by rule {violation.rule_id}",
            violation.stage, violation.rule_id, list(violation.owasp), call_id,
        )
    if isinstance(exc, exc_module.QuarantinedError):
        return ErrorFields(403, "quarantined", CallStatus.BLOCKED, exc.reason,
                           StageName.behavior, "circuit_breaker", call_id=call_id)
    if isinstance(exc, exc_module.RateLimitedError):
        return ErrorFields(429, "rate_limited", CallStatus.BLOCKED, exc.reason,
                           StageName.behavior, "rate_limit", call_id=call_id)
    if isinstance(exc, exc_module.BudgetExceededError):
        return ErrorFields(403, "budget_exceeded", CallStatus.BLOCKED, exc.reason,
                           StageName.resource, call_id=call_id)
    if isinstance(exc, exc_module.UpstreamProviderError | exc_module.AgentUnavailableError):
        return ErrorFields(502, "upstream_error", CallStatus.BLOCKED, exc.reason, call_id=call_id)
    if isinstance(exc, exc_module.PolicyValidationError):
        return ErrorFields(422, "validation_error", CallStatus.BLOCKED, exc.reason,
                           call_id=call_id)
    if isinstance(exc, _NOT_FOUND_CLASSES):
        return ErrorFields(404, "not_found", CallStatus.BLOCKED, str(exc), call_id=call_id)
    return None


async def _handle_control_layer_error(request: Request, exc: Exception) -> JSONResponse:
    fields = describe_error(exc)
    if fields is None:
        raise exc
    return error_response(
        fields.http_status, fields.code, fields.status, fields.reason,
        stage=fields.stage, rule_id=fields.rule_id, owasp=fields.owasp, call_id=fields.call_id,
    )


async def _handle_request_validation(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return error_response(422, "validation_error", CallStatus.BLOCKED, str(exc))


_NOT_FOUND_CLASSES: tuple[type[Exception], ...] = (
    exc_module.ApprovalNotFoundError,
    exc_module.CallNotFoundError,
    exc_module.UnknownToolError,
    ExportNotAvailableError,
    RunNotFoundError,
)

_HANDLED_CLASSES: tuple[type[Exception], ...] = (
    exc_module.IdentityRejectedError,
    exc_module.PolicyViolationError,
    exc_module.QuarantinedError,
    exc_module.RateLimitedError,
    exc_module.BudgetExceededError,
    exc_module.UpstreamProviderError,
    exc_module.AgentUnavailableError,
    exc_module.PolicyValidationError,
    *_NOT_FOUND_CLASSES,
)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _handle_request_validation)
    for exc_class in _HANDLED_CLASSES:
        app.add_exception_handler(exc_class, _handle_control_layer_error)
