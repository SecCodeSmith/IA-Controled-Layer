from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Sequence
from datetime import UTC, datetime

from control_layer.application.events.feed_broadcaster import FeedBroadcaster, FeedEvent
from control_layer.application.selftest.attack_run import (
    AttackRun,
    AttackRunScenario,
    AttackRunSummary,
)
from control_layer.application.selftest.scenario_executor import ScenarioExecutor, ScenarioStatus
from control_layer.domain.exceptions import ControlLayerError
from control_layer.selftest.scenarios import SCENARIOS, Scenario

_MAX_RUNS = 20


class RunNotFoundError(ControlLayerError):
    def __init__(self, run_id: str) -> None:
        super().__init__(f"attack suite run not found: {run_id}")
        self.run_id = run_id


class AttackRunManager:
    def __init__(
        self,
        executor_factory: Callable[[str], ScenarioExecutor],
        broadcaster: FeedBroadcaster,
        scenarios: Sequence[Scenario] | None = None,
    ) -> None:
        self._executor_factory = executor_factory
        self._broadcaster = broadcaster
        self._scenarios: list[Scenario] = list(scenarios) if scenarios is not None else list(
            SCENARIOS
        )
        self._runs: dict[str, AttackRun] = {}
        self._run_order: list[str] = []
        self._run_broadcasters: dict[str, FeedBroadcaster] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._next_number = 1

    async def start(self, agent: str) -> AttackRun:
        number = self._next_number
        self._next_number += 1
        run_id = f"run_{number}"

        scenario_views = [AttackRunScenario.from_scenario(s) for s in self._scenarios]
        run = AttackRun(
            run_id=run_id,
            number=number,
            agent=agent,
            started_at=datetime.now(UTC),
            scenarios=scenario_views,
            summary=AttackRunSummary.from_scenarios(scenario_views),
        )

        self._runs[run_id] = run
        self._run_order.append(run_id)
        self._run_broadcasters[run_id] = FeedBroadcaster()
        await self._evict_old_runs()

        self._tasks[run_id] = asyncio.create_task(self._execute(run_id, agent))
        return run

    async def _evict_old_runs(self) -> None:
        while len(self._run_order) > _MAX_RUNS:
            oldest = self._run_order.pop(0)
            self._runs.pop(oldest, None)
            self._tasks.pop(oldest, None)
            old_broadcaster = self._run_broadcasters.pop(oldest, None)
            if old_broadcaster is not None:
                await old_broadcaster.close()

    def get(self, run_id: str) -> AttackRun:
        run = self._runs.get(run_id)
        if run is None:
            raise RunNotFoundError(run_id)
        return run

    async def wait(self, run_id: str) -> AttackRun:
        task = self._tasks.get(run_id)
        if task is not None:
            await task
        return self.get(run_id)

    def subscribe(self, run_id: str) -> AsyncIterator[FeedEvent]:
        run = self.get(run_id)
        run_broadcaster = self._run_broadcasters[run_id]
        live = run_broadcaster.subscribe()
        replay = [
            FeedEvent(event="scenario", data=self._scenario_event(view))
            for view in run.scenarios
        ]
        return self._replay_then_stream(replay, live)

    @staticmethod
    async def _replay_then_stream(
        replay: list[FeedEvent], live: AsyncIterator[FeedEvent]
    ) -> AsyncIterator[FeedEvent]:
        for event in replay:
            yield event
        async for event in live:
            yield event

    async def _execute(self, run_id: str, agent: str) -> None:
        run = self._runs[run_id]
        run_broadcaster = self._run_broadcasters[run_id]
        executor = self._executor_factory(agent)

        for scenario, view in zip(self._scenarios, run.scenarios, strict=True):
            view.status = ScenarioStatus.RUNNING
            await self._emit(run_broadcaster, "scenario", self._scenario_event(view))

            result = await executor.run(scenario, tier=agent)

            view.status = result.status
            view.observed = result.observed
            view.duration_ms = result.duration_ms
            await self._emit(run_broadcaster, "scenario", self._scenario_event(view))

        run.finished_at = datetime.now(UTC)
        run.summary = AttackRunSummary.from_scenarios(run.scenarios)
        await self._emit(
            run_broadcaster,
            "run_complete",
            {"run_id": run_id, "summary": run.summary.model_dump()},
        )

    async def _emit(self, run_broadcaster: FeedBroadcaster, event: str, data: dict) -> None:
        await run_broadcaster.publish(event, data)
        await self._broadcaster.publish(event, data)

    @staticmethod
    def _scenario_event(view: AttackRunScenario) -> dict:
        observed = None
        if view.observed is not None:
            observed = {
                "status": view.observed.status,
                "stage": view.observed.stage,
                "rule_id": view.observed.rule_id,
            }
        return {
            "id": view.id,
            "status": view.status,
            "observed": observed,
            "duration_ms": view.duration_ms,
        }
