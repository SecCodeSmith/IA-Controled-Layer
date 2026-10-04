from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from typing import Literal, Protocol

from pydantic import BaseModel

from control_layer.application.events.feed_broadcaster import FeedBroadcaster, FeedEvent
from control_layer.domain.exceptions import ControlLayerError
from control_layer.domain.models.classifier import RetrainResult

_MAX_JOBS = 10
_TERMINAL_EVENTS = frozenset({"retrain_complete", "retrain_failed"})


class Retrainer(Protocol):
    async def execute(
        self,
        include_pending: bool = False,
        seed: int | None = None,
        progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> RetrainResult: ...


class RetrainAlreadyRunningError(ControlLayerError):
    def __init__(self, job_id: str) -> None:
        super().__init__(f"a retrain job is already running: {job_id}")
        self.job_id = job_id


class RetrainJobNotFoundError(ControlLayerError):
    def __init__(self, job_id: str) -> None:
        super().__init__(f"retrain job not found: {job_id}")
        self.job_id = job_id


class RetrainJob(BaseModel):
    job_id: str
    status: Literal["running", "complete", "failed"] = "running"
    started_at: datetime
    finished_at: datetime | None = None
    result: RetrainResult | None = None
    error: str | None = None


class _JobChannel:
    def __init__(self) -> None:
        self.history: list[FeedEvent] = []
        self.live = FeedBroadcaster()


class RetrainJobManager:
    def __init__(self, retrainer: Retrainer, broadcaster: FeedBroadcaster) -> None:
        self._retrainer = retrainer
        self._broadcaster = broadcaster
        self._jobs: dict[str, RetrainJob] = {}
        self._channels: dict[str, _JobChannel] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._running_id: str | None = None
        self._last_result: RetrainResult | None = None
        self._next_number = 1

    @property
    def running(self) -> bool:
        return self._running_id is not None

    @property
    def last_result(self) -> RetrainResult | None:
        return self._last_result

    async def start(self, include_pending: bool = False, seed: int | None = None) -> RetrainJob:
        if self._running_id is not None:
            raise RetrainAlreadyRunningError(self._running_id)
        job_id = f"retrain_{self._next_number}"
        self._next_number += 1
        job = RetrainJob(job_id=job_id, started_at=datetime.now(UTC))
        self._jobs[job_id] = job
        self._channels[job_id] = _JobChannel()
        self._running_id = job_id
        await self._evict_old_jobs()
        self._tasks[job_id] = asyncio.create_task(self._execute(job, include_pending, seed))
        return job

    def get(self, job_id: str) -> RetrainJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise RetrainJobNotFoundError(job_id)
        return job

    async def wait(self, job_id: str) -> RetrainJob:
        task = self._tasks.get(job_id)
        if task is not None:
            await task
        return self.get(job_id)

    def subscribe(self, job_id: str) -> AsyncIterator[FeedEvent]:
        self.get(job_id)
        channel = self._channels[job_id]
        replay = list(channel.history)
        live = None if self._finished(replay) else channel.live.subscribe()
        return self._replay_then_stream(replay, live)

    @staticmethod
    def _finished(events: list[FeedEvent]) -> bool:
        return any(event.event in _TERMINAL_EVENTS for event in events)

    @staticmethod
    async def _replay_then_stream(
        replay: list[FeedEvent], live: AsyncIterator[FeedEvent] | None
    ) -> AsyncIterator[FeedEvent]:
        for event in replay:
            yield event
        if live is None:
            return
        async for event in live:
            yield event
            if event.event in _TERMINAL_EVENTS:
                return

    async def _execute(self, job: RetrainJob, include_pending: bool, seed: int | None) -> None:
        async def progress(step: str) -> None:
            await self._emit(job.job_id, "retrain_progress", {"job_id": job.job_id, "step": step})

        await self._emit(job.job_id, "retrain_started", {"job_id": job.job_id})
        try:
            result = await self._retrainer.execute(
                include_pending=include_pending, seed=seed, progress=progress
            )
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc) or type(exc).__name__
            job.finished_at = datetime.now(UTC)
            self._running_id = None
            await self._emit(
                job.job_id, "retrain_failed", {"job_id": job.job_id, "error": job.error}
            )
            return
        job.status = "complete"
        job.result = result
        job.finished_at = datetime.now(UTC)
        self._last_result = result
        self._running_id = None
        await self._emit(job.job_id, "retrain_complete", result.model_dump(mode="json"))

    async def _emit(self, job_id: str, event: str, data: dict) -> None:
        channel = self._channels.get(job_id)
        if channel is not None:
            channel.history.append(FeedEvent(event=event, data=data))
            await channel.live.publish(event, data)
        await self._broadcaster.publish(event, data)

    async def _evict_old_jobs(self) -> None:
        while len(self._jobs) > _MAX_JOBS:
            oldest = next(iter(self._jobs))
            self._jobs.pop(oldest)
            self._tasks.pop(oldest, None)
            channel = self._channels.pop(oldest, None)
            if channel is not None:
                await channel.live.close()
