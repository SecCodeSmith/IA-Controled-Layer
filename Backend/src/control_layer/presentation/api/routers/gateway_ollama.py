from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from control_layer.application.gateway import ollama_mapping as mapping
from control_layer.domain.exceptions import ControlLayerError
from control_layer.domain.models.chat import ChatCompletionRequest
from control_layer.presentation.api.dependencies import ContainerDep, gateway_session_id
from control_layer.presentation.api.error_handlers import describe_error
from control_layer.presentation.api.gateway_support import run_gateway_chat

router = APIRouter(tags=["gateway"])

_UPSTREAM_TIMEOUT_S = 10.0
_MOCK_DETAILS = {
    "family": "mock",
    "format": "mock",
    "families": ["mock"],
    "parameter_size": "0B",
    "quantization_level": "none",
}


def _synthetic_tags() -> dict[str, Any]:
    return {
        "models": [
            {
                "name": "mock",
                "model": "mock",
                "modified_at": mapping.now_rfc3339(),
                "size": 0,
                "digest": "",
                "details": dict(_MOCK_DETAILS),
            }
        ]
    }


def _synthetic_show() -> dict[str, Any]:
    return {
        "modelfile": "",
        "parameters": "",
        "template": "",
        "details": dict(_MOCK_DETAILS),
        "model_info": {"general.architecture": "mock", "mock.context_length": 8192},
        "capabilities": ["completion", "tools"],
    }


async def _pass_through(
    request: Request,
    container: ContainerDep,
    method: str,
    path: str,
    synthetic: Callable[[], dict[str, Any]],
    body: dict[str, Any] | None = None,
) -> Response:
    if container.model_provider.describe().name != "mock":
        base = container.settings.ollama_base_url.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=_UPSTREAM_TIMEOUT_S) as client:
                upstream = await client.request(method, f"{base}{path}", json=body)
        except httpx.HTTPError:
            pass
        else:
            return Response(
                content=upstream.content,
                status_code=upstream.status_code,
                media_type=upstream.headers.get("content-type", "application/json"),
            )
    return JSONResponse(synthetic())


@router.get("/api/tags")
async def tags(request: Request, container: ContainerDep) -> Response:
    return await _pass_through(request, container, "GET", "/api/tags", _synthetic_tags)


@router.post("/api/show")
async def show(request: Request, container: ContainerDep) -> Response:
    body = await _json_body(request)
    return await _pass_through(request, container, "POST", "/api/show", _synthetic_show, body)


@router.get("/api/version")
async def version(request: Request, container: ContainerDep) -> Response:
    return await _pass_through(
        request, container, "GET", "/api/version", lambda: {"version": "0.0.0-control-layer"}
    )


@router.get("/api/ps")
async def ps(request: Request, container: ContainerDep) -> Response:
    return await _pass_through(request, container, "GET", "/api/ps", lambda: {"models": []})


async def _json_body(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


async def _lines(lines: list[str]) -> AsyncIterator[str]:
    for line in lines:
        yield line
        await asyncio.sleep(0)


async def _handle(
    request: Request,
    container: ContainerDep,
    to_request: Callable[[dict[str, Any]], ChatCompletionRequest],
    single: Callable[[str, mapping.GatewayReply, int, int], dict[str, Any]],
    stream: Callable[[str, mapping.GatewayReply, int, int], list[dict[str, Any]]],
) -> Response:
    body = await _json_body(request)
    if not body.get("model") or not (body.get("messages") or body.get("prompt") is not None):
        return _error(400, "invalid request: model and messages (or prompt) are required")
    chat_request = to_request(body)
    try:
        token = await container.gateway_credentials.resolve(request.headers.get("authorization"))
        session = gateway_session_id(
            token, request.headers.get("x-session-id"), request.headers.get("user-agent")
        )
        result = await run_gateway_chat(container, token, session, chat_request)
    except ControlLayerError as exc:
        fields = describe_error(exc)
        if fields is None:
            raise
        return _error(fields.http_status, fields.reason)
    model = chat_request.model
    if body.get("stream", True):
        lines = mapping.ndjson(stream(model, result.reply, result.total_ns, result.eval_ns))
        return StreamingResponse(
            _lines(lines),
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    payload = single(model, result.reply, result.total_ns, result.eval_ns)
    return Response(json.dumps(payload), media_type="application/json")


@router.post("/api/chat")
async def chat(request: Request, container: ContainerDep) -> Response:
    return await _handle(
        request,
        container,
        mapping.ollama_chat_to_request,
        mapping.ollama_chat_response,
        mapping.ollama_chat_stream,
    )


@router.post("/api/generate")
async def generate(request: Request, container: ContainerDep) -> Response:
    return await _handle(
        request,
        container,
        mapping.ollama_generate_to_request,
        mapping.ollama_generate_response,
        mapping.ollama_generate_stream,
    )
