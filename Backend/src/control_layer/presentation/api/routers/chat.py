from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response, StreamingResponse

from control_layer.application.gateway.ollama_mapping import (
    control_layer_extension,
    openai_stream_frames,
)
from control_layer.domain.models.chat import ChatCompletionRequest
from control_layer.presentation.api.dependencies import (
    ContainerDep,
    GatewaySessionDep,
    GatewayTokenDep,
)
from control_layer.presentation.api.gateway_support import run_gateway_chat

router = APIRouter(prefix="/v1", tags=["proxy"])


async def _frames(frames: list[str]) -> AsyncIterator[str]:
    for frame in frames:
        yield frame
        await asyncio.sleep(0)


@router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    token: GatewayTokenDep,
    session: GatewaySessionDep,
    container: ContainerDep,
) -> Response:
    if request.stream:
        result = await run_gateway_chat(container, token, session, request)
        frames = openai_stream_frames(request.model, result.reply, result.control_layer)
        return StreamingResponse(
            _frames(frames),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    outcome = await container.chat_completion.execute(token, session, request)
    body = outcome.response.model_dump(mode="json", exclude_none=True)
    for choice in body.get("choices", []):
        choice.get("message", {}).setdefault("content", None)
    body["control_layer"] = control_layer_extension(outcome)
    return JSONResponse(body)
