from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from control_layer.domain.models.chat import ChatCompletionRequest
from control_layer.domain.models.enums import CallStatus
from control_layer.presentation.api.dependencies import BearerDep, ContainerDep, SessionDep
from control_layer.presentation.api.error_handlers import error_response

router = APIRouter(prefix="/v1", tags=["proxy"])


@router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    token: BearerDep,
    session: SessionDep,
    container: ContainerDep,
) -> JSONResponse:
    if request.stream:
        return error_response(
            400,
            "streaming_not_supported",
            CallStatus.BLOCKED,
            "Streaming responses are not supported; send stream=false",
        )
    outcome = await container.chat_completion.execute(token, session, request)
    body = outcome.response.model_dump(mode="json", exclude_none=True)
    for choice in body.get("choices", []):
        choice.get("message", {}).setdefault("content", None)
    body["control_layer"] = {
        "call_id": outcome.call_id,
        "status": outcome.status.value,
        "stage": outcome.stage.value if outcome.stage else None,
        "rule_id": outcome.rule_id,
        "reason": outcome.reason,
        "items_masked": outcome.items_masked,
        "proxy_latency_ms": outcome.proxy_latency_ms,
        "upstream_latency_ms": outcome.upstream_latency_ms,
    }
    return JSONResponse(body)
