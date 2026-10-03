"""Thin async HTTP client for the AI Control Layer (`WIKI/api-contract.md`).

The demo agent never imports control_layer code; every call here crosses a
real HTTP boundary (or, in tests, an `httpx.MockTransport` fake of it). The
caller's bearer token is forwarded unchanged on every `/v1/*` call.
"""

from __future__ import annotations

from typing import Any

import httpx

from demo_agent.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    MeResponse,
    RejectResult,
    ToolCallOutcome,
    ToolCallRequest,
    ToolDescriptor,
)


class ControlLayerDenied(Exception):
    def __init__(
        self,
        http_status: int,
        code: str,
        status: str | None = None,
        stage: str | None = None,
        rule_id: str | None = None,
        reason: str | None = None,
        owasp: list[str] | None = None,
        call_id: str | None = None,
    ) -> None:
        super().__init__(reason or code)
        self.http_status = http_status
        self.code = code
        self.status = status
        self.stage = stage
        self.rule_id = rule_id
        self.reason = reason
        self.owasp = owasp or []
        self.call_id = call_id


class ControlLayerUnreachable(Exception):
    pass


def _raise_for_error(response: httpx.Response) -> None:
    try:
        error = response.json()["error"]
    except (ValueError, KeyError, TypeError):
        raise ControlLayerDenied(
            http_status=response.status_code,
            code="upstream_error",
            reason=response.text or "Unrecognized error response from the control layer.",
        ) from None
    raise ControlLayerDenied(
        http_status=response.status_code,
        code=error.get("code", "unknown"),
        status=error.get("status"),
        stage=error.get("stage"),
        rule_id=error.get("rule_id"),
        reason=error.get("reason"),
        owasp=error.get("owasp"),
        call_id=error.get("call_id"),
    )


class ControlLayerClient:
    def __init__(
        self,
        base_url: str,
        timeout_s: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout_s, transport=transport)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        session_id: str | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        if session_id:
            headers["X-Session-Id"] = session_id
        try:
            response = await self._client.request(method, path, headers=headers, json=json_body)
        except httpx.HTTPError as exc:
            raise ControlLayerUnreachable(str(exc)) from exc
        if response.status_code >= 400:
            _raise_for_error(response)
        try:
            return response.json()
        except ValueError as exc:
            raise ControlLayerUnreachable(f"invalid JSON from control layer: {exc}") from exc

    async def me(self, token: str, session_id: str | None = None) -> MeResponse:
        payload = await self._request("GET", "/v1/me", token=token, session_id=session_id)
        return MeResponse.model_validate(payload)

    async def list_tools(self, token: str, session_id: str | None = None) -> list[ToolDescriptor]:
        payload = await self._request("GET", "/v1/tools", token=token, session_id=session_id)
        return [ToolDescriptor.model_validate(item) for item in payload["tools"]]

    async def chat_completion(
        self,
        token: str,
        request: ChatCompletionRequest,
        session_id: str | None = None,
    ) -> ChatCompletionResponse:
        payload = await self._request(
            "POST",
            "/v1/chat/completions",
            token=token,
            session_id=session_id,
            json_body=request.model_dump(exclude_none=True),
        )
        return ChatCompletionResponse.model_validate(payload)

    async def call_tool(
        self,
        token: str,
        request: ToolCallRequest,
        session_id: str | None = None,
    ) -> ToolCallOutcome:
        payload = await self._request(
            "POST",
            "/v1/tools/call",
            token=token,
            session_id=session_id or request.session_id,
            json_body=request.model_dump(exclude_none=True),
        )
        return ToolCallOutcome.model_validate(payload)

    async def approve(
        self, token: str, approval_id: str, session_id: str | None = None
    ) -> ToolCallOutcome:
        payload = await self._request(
            "POST", f"/v1/approvals/{approval_id}/approve", token=token, session_id=session_id
        )
        return ToolCallOutcome.model_validate(payload)

    async def reject(
        self, token: str, approval_id: str, session_id: str | None = None
    ) -> RejectResult:
        payload = await self._request(
            "POST", f"/v1/approvals/{approval_id}/reject", token=token, session_id=session_id
        )
        return RejectResult.model_validate(payload)

    async def health(self) -> dict[str, Any]:
        return await self._request("GET", "/health")
