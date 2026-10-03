"""Shared fakes for demo_agent unit tests.

`ScriptedBackend` stands in for the control layer: it answers `/v1/*` and
`/health` with pre-scripted (status, body) pairs, in the exact shapes from
`WIKI/api-contract.md`, and records every request for assertions. The demo
agent under test never imports control_layer code; everything crosses this
fake HTTP boundary via `httpx.MockTransport`.
"""

from __future__ import annotations

import json as _json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from demo_agent.control_layer_client import ControlLayerClient
from demo_agent.main import create_app
from demo_agent.session_store import SessionStore
from demo_agent.settings import Settings

ANNA_IDENTITY: dict[str, Any] = {
    "sub": "anna.kowalska",
    "name": "Anna Kowalska",
    "role": "developer",
    "location": "Krakow, PL",
    "region": "PL",
    "agent_id": "agent-anna-dev-7f3a",
}


def ok(body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    return (200, body)


def me_body(tokens_used: int = 3420, tokens_limit: int = 10000) -> dict[str, Any]:
    return {
        "identity": ANNA_IDENTITY,
        "tools": [],
        "policy": {"name": "roles.developer", "version": 3},
        "budget": {
            "tokens_used": tokens_used,
            "tokens_limit": tokens_limit,
            "cost_used_usd": 0.001,
            "cost_limit_usd": 1.0,
            "resets_at": "2026-10-05T00:00:00Z",
        },
        "risk": {"score": 12, "level": "low"},
        "provider": {"name": "ollama", "model": "qwen2.5:7b"},
    }


def tool_descriptor(
    server: str,
    name: str,
    description: str = "A demo tool.",
    input_schema: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "server": server,
        "name": name,
        "qualified_name": f"{server}.{name}",
        "description": description,
        "input_schema": input_schema or {"type": "object", "properties": {}},
        "tags": tags or [],
        "data_region": None,
        "scope": "read+write",
    }


def tools_body(*descriptors: dict[str, Any]) -> dict[str, Any]:
    return {"tools": list(descriptors)}


def completion_body(
    *,
    content: str | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    status: str = "ALLOWED",
    stage: str | None = None,
    rule_id: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    finish_reason = "stop"
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
        finish_reason = "tool_calls"
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 0,
        "model": "qwen2.5:7b",
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        "control_layer": {
            "call_id": "c_chat",
            "status": status,
            "stage": stage,
            "rule_id": rule_id,
            "reason": reason,
            "items_masked": 0,
            "proxy_latency_ms": 1.0,
            "upstream_latency_ms": 100.0,
        },
    }


def tool_call_function(
    name: str, arguments: dict[str, Any] | str, call_id: str = "call_1"
) -> dict[str, Any]:
    args_str = arguments if isinstance(arguments, str) else _json.dumps(arguments)
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": args_str}}


def tool_outcome_body(
    *,
    call_id: str,
    status: str,
    content_text: str,
    stage: str | None = None,
    rule_id: str | None = None,
    reason: str | None = None,
    items_masked: int = 0,
) -> dict[str, Any]:
    return {
        "call_id": call_id,
        "status": status,
        "stage": stage,
        "rule_id": rule_id,
        "reason": reason,
        "items_masked": items_masked,
        "result": {"content_text": content_text, "structured_content": None, "is_error": False},
    }


def escalated_body(
    *,
    call_id: str,
    approval_id: str,
    rule_id: str,
    reason: str,
    expires_at: str = "2026-10-03T11:00:00Z",
) -> dict[str, Any]:
    return {
        "call_id": call_id,
        "status": "ESCALATED",
        "stage": "authorization",
        "rule_id": rule_id,
        "reason": reason,
        "items_masked": 0,
        "approval": {"id": approval_id, "expires_at": expires_at},
    }


def error_body(
    *,
    code: str,
    status: str | None,
    stage: str | None,
    rule_id: str | None,
    reason: str,
    call_id: str = "c_err",
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "status": status,
            "stage": stage,
            "rule_id": rule_id,
            "reason": reason,
            "owasp": [],
            "call_id": call_id,
        }
    }


class ScriptedBackend:
    def __init__(self) -> None:
        self.me_queue: list[tuple[int, dict[str, Any]]] = []
        self.tools_response: dict[str, Any] = {"tools": []}
        self.completion_queue: list[tuple[int, dict[str, Any]]] = []
        self.tool_call_queue: list[tuple[int, dict[str, Any]]] = []
        self.approve_queue: list[tuple[int, dict[str, Any]]] = []
        self.reject_queue: list[tuple[int, dict[str, Any]]] = []
        self.health_response: tuple[int, dict[str, Any]] = ok(
            {"status": "ok", "provider": {"name": "ollama", "model": "qwen2.5:7b"}}
        )
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/v1/me" and request.method == "GET":
            status, body = self.me_queue.pop(0) if self.me_queue else ok(me_body())
            return httpx.Response(status, json=body)
        if path == "/v1/tools" and request.method == "GET":
            return httpx.Response(200, json=self.tools_response)
        if path == "/v1/chat/completions" and request.method == "POST":
            return self._pop(self.completion_queue)
        if path == "/v1/tools/call" and request.method == "POST":
            return self._pop(self.tool_call_queue)
        if path.startswith("/v1/approvals/") and path.endswith("/approve"):
            return self._pop(self.approve_queue)
        if path.startswith("/v1/approvals/") and path.endswith("/reject"):
            return self._pop(self.reject_queue)
        if path == "/health" and request.method == "GET":
            status, body = self.health_response
            return httpx.Response(status, json=body)
        return httpx.Response(
            404,
            json=error_body(
                code="not_found",
                status=None,
                stage=None,
                rule_id=None,
                reason=f"no route for {path}",
            ),
        )

    @staticmethod
    def _pop(queue: list[tuple[int, dict[str, Any]]]) -> httpx.Response:
        if not queue:
            raise AssertionError("scripted backend queue exhausted")
        status, body = queue.pop(0)
        return httpx.Response(status, json=body)

    def requests_to(self, path: str) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.path == path]


@pytest.fixture
def backend() -> ScriptedBackend:
    return ScriptedBackend()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        control_layer_url="http://control-layer.test",
        max_iterations=6,
        temperature=0.0,
        request_timeout_s=5.0,
    )


@pytest.fixture
def control_layer_client(backend: ScriptedBackend, settings: Settings) -> ControlLayerClient:
    return ControlLayerClient(
        base_url=settings.control_layer_url,
        timeout_s=settings.request_timeout_s,
        transport=httpx.MockTransport(backend.handler),
    )


@pytest.fixture
def session_store() -> SessionStore:
    return SessionStore()


@pytest.fixture
def test_app(backend: ScriptedBackend, settings: Settings):
    return create_app(settings=settings, transport=httpx.MockTransport(backend.handler))


@pytest.fixture
def test_client(test_app):
    with TestClient(test_app) as client:
        yield client
