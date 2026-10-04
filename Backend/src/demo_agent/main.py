"""Demo agent FastAPI app: a pure HTTP client of the AI Control Layer.

Endpoints follow WIKI/api-contract.md, section "Demo agent service":
`POST /agent/chat`, `POST /agent/approvals/{id}`, `GET /agent/health`.
"""

from __future__ import annotations

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from demo_agent.agent_loop import AgentLoop, UnknownApprovalError, fetch_agent_budget
from demo_agent.control_layer_client import (
    ControlLayerClient,
    ControlLayerDenied,
    ControlLayerUnreachable,
)
from demo_agent.schemas import (
    AgentApprovalRequest,
    AgentChatRequest,
    AgentChatResponse,
    AgentHealthResponse,
    ProviderInfo,
)
from demo_agent.session_store import SessionStore
from demo_agent.settings import Settings, get_settings


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    return authorization.split(" ", 1)[1]


def _denied_response(exc: ControlLayerDenied) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error": {
                "code": exc.code,
                "status": exc.status,
                "stage": exc.stage,
                "rule_id": exc.rule_id,
                "reason": exc.reason,
                "owasp": exc.owasp,
                "call_id": exc.call_id,
            }
        },
    )


def create_app(
    settings: Settings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="AI Control Layer demo agent")

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    client = ControlLayerClient(
        base_url=settings.control_layer_url,
        timeout_s=settings.request_timeout_s,
        transport=transport,
    )
    sessions = SessionStore(ttl_s=settings.session_ttl_s)
    loop = AgentLoop(client=client, sessions=sessions, settings=settings)

    app.state.settings = settings
    app.state.client = client
    app.state.sessions = sessions
    app.state.agent_loop = loop

    @app.exception_handler(ControlLayerDenied)
    async def handle_denied(_: Request, exc: ControlLayerDenied) -> JSONResponse:
        return _denied_response(exc)

    @app.exception_handler(ControlLayerUnreachable)
    async def handle_unreachable(_: Request, exc: ControlLayerUnreachable) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content={"error": {"code": "upstream_error", "reason": str(exc)}},
        )

    @app.exception_handler(UnknownApprovalError)
    async def handle_unknown_approval(_: Request, exc: UnknownApprovalError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "validation_error", "reason": str(exc)}},
        )

    @app.post("/agent/chat", response_model=AgentChatResponse)
    async def agent_chat(
        payload: AgentChatRequest,
        authorization: str | None = Header(default=None),
    ) -> AgentChatResponse:
        token = _bearer_token(authorization)
        events = await loop.run_turn(token, payload.session_id, payload.message)
        budget = await fetch_agent_budget(client, token, payload.session_id)
        return AgentChatResponse(session_id=payload.session_id, events=events, budget=budget)

    @app.post("/agent/approvals/{approval_id}", response_model=AgentChatResponse)
    async def agent_approval(
        approval_id: str,
        payload: AgentApprovalRequest,
        authorization: str | None = Header(default=None),
    ) -> AgentChatResponse:
        token = _bearer_token(authorization)
        events = await loop.resume_after_approval(
            token, payload.session_id, approval_id, payload.decision
        )
        budget = await fetch_agent_budget(client, token, payload.session_id)
        return AgentChatResponse(session_id=payload.session_id, events=events, budget=budget)

    @app.post("/agent/sessions/{session_id}/reset")
    async def agent_session_reset(
        session_id: str, authorization: str | None = Header(default=None)
    ) -> dict:
        token = _bearer_token(authorization)
        await loop.reset_session(token, session_id)
        return {"session_id": session_id, "cleared": True}

    @app.get("/agent/health", response_model=AgentHealthResponse)
    async def agent_health() -> AgentHealthResponse:
        try:
            payload = await client.health()
        except ControlLayerUnreachable:
            return AgentHealthResponse(status="ok", control_layer="unreachable", provider=None)
        provider_raw = payload.get("provider")
        provider = ProviderInfo.model_validate(provider_raw) if provider_raw else None
        return AgentHealthResponse(
            status="ok", control_layer=settings.control_layer_url, provider=provider
        )

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("demo_agent.main:app", host="0.0.0.0", port=get_settings().port)
