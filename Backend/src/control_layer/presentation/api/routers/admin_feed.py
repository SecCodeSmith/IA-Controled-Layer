from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from control_layer.application.use_cases.admin.feed import FeedQuery
from control_layer.presentation.api.dependencies import AdminDeps, ContainerDep
from control_layer.presentation.api.mappers import feed_row
from control_layer.presentation.api.schemas.feed import FeedListResponse

router = APIRouter(prefix="/api/feed", tags=["admin"], dependencies=AdminDeps)


@router.get("", response_model=FeedListResponse)
async def feed(
    container: ContainerDep,
    user: str | None = None,
    role: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> FeedListResponse:
    records = await container.list_feed.execute(
        FeedQuery(user=user, role=role, status=status, limit=limit)
    )
    return FeedListResponse(items=[feed_row(r) for r in records])


@router.get("/stream")
async def feed_stream(container: ContainerDep) -> EventSourceResponse:
    async def events() -> AsyncIterator[dict[str, str]]:
        async for event in container.stream_feed.stream():
            yield {"event": event.event, "data": json.dumps(event.data, default=str)}

    return EventSourceResponse(events())
