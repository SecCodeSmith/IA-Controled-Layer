from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import pytest

from control_layer.application.classifier.retrain_job_manager import (
    RetrainAlreadyRunningError,
    RetrainJobManager,
    RetrainJobNotFoundError,
)
from control_layer.application.events.feed_broadcaster import FeedBroadcaster
from control_layer.domain.models.classifier import RetrainResult

_RESULT = RetrainResult(
    f1=0.91,
    passed_gate=True,
    swapped=True,
    n_base=600,
    n_feedback=3,
    version=1,
    trained_at=datetime(2026, 10, 4, 12, 0, tzinfo=UTC),
)


class FakeRetrain:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.release = asyncio.Event()
        self.calls: list[tuple[bool, int]] = []

    async def execute(
        self,
        include_pending: bool = False,
        seed: int | None = None,
        progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> RetrainResult:
        self.calls.append((include_pending, seed))
        await self.release.wait()
        if progress is not None:
            await progress("loading")
            await progress("training")
        if self.error is not None:
            raise self.error
        return _RESULT


async def _collect(manager: RetrainJobManager, job_id: str) -> list[tuple[str, dict]]:
    return [(event.event, event.data) async for event in manager.subscribe(job_id)]


async def test_start_returns_running_job_and_forwards_arguments() -> None:
    retrain = FakeRetrain()
    manager = RetrainJobManager(retrain, FeedBroadcaster())

    job = await manager.start(include_pending=True, seed=7)
    await asyncio.sleep(0)

    assert job.job_id == "retrain_1"
    assert job.status == "running"
    assert job.finished_at is None
    assert manager.running is True
    assert retrain.calls == [(True, 7)]
    retrain.release.set()
    await manager.wait(job.job_id)


async def test_second_start_while_running_is_rejected() -> None:
    retrain = FakeRetrain()
    manager = RetrainJobManager(retrain, FeedBroadcaster())
    job = await manager.start()

    with pytest.raises(RetrainAlreadyRunningError):
        await manager.start()

    retrain.release.set()
    await manager.wait(job.job_id)
    next_job = await manager.start()
    assert next_job.job_id == "retrain_2"
    await manager.wait(next_job.job_id)


async def test_completed_job_streams_events_in_order_and_records_result() -> None:
    retrain = FakeRetrain()
    retrain.release.set()
    manager = RetrainJobManager(retrain, FeedBroadcaster())

    job = await manager.start()
    finished = await manager.wait(job.job_id)
    events = await _collect(manager, job.job_id)

    assert [name for name, _ in events] == [
        "retrain_started",
        "retrain_progress",
        "retrain_progress",
        "retrain_complete",
    ]
    assert [data["step"] for name, data in events if name == "retrain_progress"] == [
        "loading",
        "training",
    ]
    assert events[-1][1] == _RESULT.model_dump(mode="json")
    assert finished.status == "complete"
    assert finished.result == _RESULT
    assert finished.finished_at is not None
    assert manager.running is False
    assert manager.last_result == _RESULT


async def test_live_subscriber_receives_events_until_completion() -> None:
    retrain = FakeRetrain()
    manager = RetrainJobManager(retrain, FeedBroadcaster())
    job = await manager.start()

    collector = asyncio.create_task(_collect(manager, job.job_id))
    await asyncio.sleep(0)
    retrain.release.set()
    events = await asyncio.wait_for(collector, timeout=2)

    assert [name for name, _ in events][0] == "retrain_started"
    assert [name for name, _ in events][-1] == "retrain_complete"
    assert len([name for name, _ in events if name == "retrain_started"]) == 1


async def test_failure_emits_failed_event_and_marks_job_failed() -> None:
    retrain = FakeRetrain(error=RuntimeError("dataset missing"))
    retrain.release.set()
    manager = RetrainJobManager(retrain, FeedBroadcaster())

    job = await manager.start()
    finished = await manager.wait(job.job_id)
    events = await _collect(manager, job.job_id)

    assert events[-1] == ("retrain_failed", {"job_id": job.job_id, "error": "dataset missing"})
    assert finished.status == "failed"
    assert finished.error == "dataset missing"
    assert finished.result is None
    assert manager.running is False
    assert manager.last_result is None


async def test_events_are_mirrored_to_the_global_feed() -> None:
    feed = FeedBroadcaster()
    received = feed.subscribe()
    retrain = FakeRetrain()
    retrain.release.set()
    manager = RetrainJobManager(retrain, feed)

    job = await manager.start()
    await manager.wait(job.job_id)
    first = await asyncio.wait_for(anext(received), timeout=1)

    assert first.event == "retrain_started"
    assert first.data["job_id"] == job.job_id


async def test_get_returns_job_and_unknown_raises() -> None:
    retrain = FakeRetrain()
    retrain.release.set()
    manager = RetrainJobManager(retrain, FeedBroadcaster())
    job = await manager.start()
    await manager.wait(job.job_id)

    assert manager.get(job.job_id).status == "complete"
    with pytest.raises(RetrainJobNotFoundError):
        manager.get("retrain_999")
    with pytest.raises(RetrainJobNotFoundError):
        manager.subscribe("retrain_999")


async def test_only_last_ten_jobs_are_kept() -> None:
    retrain = FakeRetrain()
    retrain.release.set()
    manager = RetrainJobManager(retrain, FeedBroadcaster())

    for _ in range(11):
        job = await manager.start()
        await manager.wait(job.job_id)

    with pytest.raises(RetrainJobNotFoundError):
        manager.get("retrain_1")
    assert manager.get("retrain_11").status == "complete"
    assert manager.get("retrain_2").status == "complete"
