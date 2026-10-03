from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from control_layer.infrastructure.settings import Settings
from control_layer.presentation.api.error_handlers import register_error_handlers
from control_layer.presentation.api.routers import (
    admin_alerts,
    admin_attack_suite,
    admin_audit,
    admin_demo,
    admin_feed,
    admin_logs,
    admin_metrics,
    admin_models,
    admin_policy,
    admin_protection,
    admin_reports,
    admin_stats,
    approvals,
    auth,
    chat,
    health,
    me,
    tools,
)
from control_layer.presentation.composition_root import build_container, start, stop

_ROUTERS = (
    health,
    auth,
    me,
    chat,
    tools,
    approvals,
    admin_feed,
    admin_audit,
    admin_alerts,
    admin_stats,
    admin_metrics,
    admin_models,
    admin_policy,
    admin_protection,
    admin_logs,
    admin_reports,
    admin_attack_suite,
    admin_demo,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        container = await build_container(resolved)
        app.state.container = container
        await start(container)
        try:
            yield
        finally:
            await stop(container)

    app = FastAPI(title="AI Control Layer", version="1.0.0", lifespan=lifespan)
    origins = [o.strip() for o in resolved.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=resolved.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    for module in _ROUTERS:
        app.include_router(module.router)
    return app
