from __future__ import annotations

import asyncio

import pytest

from control_layer.application.events.feed_broadcaster import FeedBroadcaster
from control_layer.application.selftest.attack_run import AttackRunScenario
from control_layer.application.selftest.attack_run_manager import (
    AttackRunManager,
    RunNotFoundError,
)
from control_layer.application.selftest.scenario_client import StepObservation
from control_layer.application.selftest.scenario_executor import ScenarioResult, ScenarioStatus
from control_layer.domain.models.enums import CallStatus, StageName
from control_layer.selftest.scenarios import Scenario, ScenarioExpectation


def _scenario(scenario_id: str) -> Scenario:
    return Scenario(
        id=scenario_id,
        name="scenario",
        kind="negative",
        actor="anna.kowalska",
        stage="policy",
        expected=ScenarioExpectation(status=CallStatus.BLOCKED),
        owasp=[],
        steps=[],
        prompt="do it",
    )


class _FakeExecutor:
    def __init__(self, results: dict[str, ScenarioResult], concurrency_probe: list[int]) -> None:
        self._results = results
        self._probe = concurrency_probe
        self.ran: list[str] = []

    async def run(self, scenario, tier: str = "scripted") -> ScenarioResult:
        self._probe.append(1)
        assert sum(self._probe) == 1, "scenarios must run sequentially, never in parallel"
        await asyncio.sleep(0)
        self.ran.append(scenario.id)
        result = self._results[scenario.id]
        self._probe.pop()
        return result


def _result(scenario_id: str, status: ScenarioStatus) -> ScenarioResult:
    return ScenarioResult(id=scenario_id, status=status, observed=None, duration_ms=1.0)


async def test_run_numbers_increase_from_one() -> None:
    scenarios = [_scenario("a")]
    broadcaster = FeedBroadcaster()
    results = {"a": _result("a", ScenarioStatus.STOPPED)}
    manager = AttackRunManager(
        lambda agent: _FakeExecutor(results, []), broadcaster, scenarios=scenarios
    )

    run1 = await manager.start("scripted")
    await manager.wait(run1.run_id)
    run2 = await manager.start("scripted")
    await manager.wait(run2.run_id)

    assert run1.number == 1
    assert run2.number == 2
    assert run1.run_id == "run_1"
    assert run2.run_id == "run_2"


async def test_scenarios_execute_sequentially_never_in_parallel() -> None:
    scenarios = [_scenario("a"), _scenario("b"), _scenario("c")]
    broadcaster = FeedBroadcaster()
    results = {s.id: _result(s.id, ScenarioStatus.STOPPED) for s in scenarios}
    probe: list[int] = []
    executor = _FakeExecutor(results, probe)
    manager = AttackRunManager(lambda agent: executor, broadcaster, scenarios=scenarios)

    run = await manager.start("scripted")
    final = await manager.wait(run.run_id)

    assert executor.ran == ["a", "b", "c"]
    assert all(s.status == ScenarioStatus.STOPPED for s in final.scenarios)
    assert final.finished_at is not None


async def test_executor_factory_receives_the_requested_agent() -> None:
    scenarios = [_scenario("a")]
    broadcaster = FeedBroadcaster()
    results = {"a": _result("a", ScenarioStatus.NOT_ATTEMPTED)}
    seen_agents: list[str] = []

    def factory(agent: str) -> _FakeExecutor:
        seen_agents.append(agent)
        return _FakeExecutor(results, [])

    manager = AttackRunManager(factory, broadcaster, scenarios=scenarios)
    run = await manager.start("ollama")
    await manager.wait(run.run_id)

    assert seen_agents == ["ollama"]
    assert run.agent == "ollama"


async def test_summary_tallies_final_scenario_statuses() -> None:
    scenarios = [_scenario("a"), _scenario("b"), _scenario("c")]
    broadcaster = FeedBroadcaster()
    results = {
        "a": _result("a", ScenarioStatus.STOPPED),
        "b": _result("b", ScenarioStatus.SUCCEEDED),
        "c": _result("c", ScenarioStatus.NOT_ATTEMPTED),
    }
    manager = AttackRunManager(
        lambda agent: _FakeExecutor(results, []), broadcaster, scenarios=scenarios
    )

    run = await manager.start("scripted")
    final = await manager.wait(run.run_id)

    assert final.summary.stopped == 1
    assert final.summary.succeeded == 1
    assert final.summary.not_attempted == 1
    assert final.summary.pending == 0
    assert final.summary.running == 0


async def test_get_raises_for_unknown_run() -> None:
    manager = AttackRunManager(lambda agent: _FakeExecutor({}, []), FeedBroadcaster(), scenarios=[])

    with pytest.raises(RunNotFoundError):
        manager.get("run_999")


async def test_keeps_only_the_last_twenty_runs() -> None:
    scenarios = [_scenario("a")]
    results = {"a": _result("a", ScenarioStatus.STOPPED)}
    manager = AttackRunManager(
        lambda agent: _FakeExecutor(results, []), FeedBroadcaster(), scenarios=scenarios
    )

    for _ in range(25):
        run = await manager.start("scripted")
        await manager.wait(run.run_id)

    with pytest.raises(RunNotFoundError):
        manager.get("run_1")
    assert manager.get("run_25").number == 25


async def test_global_broadcaster_receives_scenario_and_run_complete_events() -> None:
    scenarios = [_scenario("a")]
    results = {"a": _result("a", ScenarioStatus.STOPPED)}
    broadcaster = FeedBroadcaster()
    subscription = broadcaster.subscribe()
    manager = AttackRunManager(
        lambda agent: _FakeExecutor(results, []), broadcaster, scenarios=scenarios
    )

    run = await manager.start("scripted")
    await manager.wait(run.run_id)

    running_event = await subscription.__anext__()
    final_event = await subscription.__anext__()
    complete_event = await subscription.__anext__()

    assert running_event.event == "scenario"
    assert running_event.data["status"] == ScenarioStatus.RUNNING
    assert final_event.event == "scenario"
    assert final_event.data["status"] == ScenarioStatus.STOPPED
    assert complete_event.event == "run_complete"
    assert complete_event.data["run_id"] == run.run_id
    assert complete_event.data["summary"]["stopped"] == 1


async def test_subscribe_replays_current_statuses_then_streams_live_updates() -> None:
    scenarios = [_scenario("a"), _scenario("b")]
    results = {
        "a": _result("a", ScenarioStatus.STOPPED),
        "b": _result("b", ScenarioStatus.PASSED),
    }
    gate = asyncio.Event()

    class _GatedExecutor:
        async def run(self, scenario, tier: str = "scripted") -> ScenarioResult:
            if scenario.id == "b":
                await gate.wait()
            return results[scenario.id]

    broadcaster = FeedBroadcaster()
    manager = AttackRunManager(lambda agent: _GatedExecutor(), broadcaster, scenarios=scenarios)

    run = await manager.start("scripted")
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    live = manager.subscribe(run.run_id)
    replay_first = await live.__anext__()
    replay_second = await live.__anext__()

    assert replay_first.data["id"] == "a"
    assert replay_second.data["id"] == "b"

    gate.set()
    final = await manager.wait(run.run_id)
    assert final.summary.stopped == 1
    assert final.summary.passed == 1


async def test_run_records_provider_model_and_protection_mode() -> None:
    scenarios = [_scenario("a")]
    results = {"a": ScenarioResult(id="a", status=ScenarioStatus.STOPPED, duration_ms=1.0)}
    manager = AttackRunManager(
        lambda agent: _FakeExecutor(results, []), FeedBroadcaster(), scenarios=scenarios
    )

    run = await manager.start("ollama", provider="mock", model="mock-1", protection_mode="off")
    await manager.wait(run.run_id)

    assert (run.provider, run.model, run.protection_mode) == ("mock", "mock-1", "off")


async def test_run_context_defaults_and_scenario_via_is_tracked() -> None:
    scenarios = [_scenario("a")]
    results = {
        "a": ScenarioResult(id="a", status=ScenarioStatus.STOPPED, duration_ms=1.0, via="agent")
    }
    manager = AttackRunManager(
        lambda agent: _FakeExecutor(results, []), FeedBroadcaster(), scenarios=scenarios
    )

    run = await manager.start("ollama")
    await manager.wait(run.run_id)

    assert (run.provider, run.model, run.protection_mode) == ("", "", "enforce")
    assert run.scenarios[0].via == "agent"


async def test_run_scenarios_carry_trace_explanation_and_error() -> None:
    scenarios = [_scenario("a"), _scenario("b")]
    stopped = ScenarioResult(
        id="a",
        status=ScenarioStatus.STOPPED,
        observed=StepObservation(
            http_status=403,
            status=CallStatus.BLOCKED,
            stage=StageName.policy,
            rule_id="r1",
            reason="why",
            target="hr-db.find_approver",
            call_id="c_5",
        ),
        duration_ms=1.0,
        trace=[
            StepObservation(
                http_status=403, status=CallStatus.BLOCKED, target="t", call_id="c_5"
            )
        ],
        explanation="Attack stopped.",
    )
    errored = ScenarioResult(
        id="b", status=ScenarioStatus.ERROR, duration_ms=1.0, error="boom", explanation="boom"
    )
    manager = AttackRunManager(
        lambda agent: _FakeExecutor({"a": stopped, "b": errored}, []),
        FeedBroadcaster(),
        scenarios=scenarios,
    )

    run = await manager.start("scripted")
    final = await manager.wait(run.run_id)
    first, second = final.scenarios
    event = AttackRunManager._scenario_event(first)

    assert first.explanation == "Attack stopped."
    assert first.trace[0].call_id == "c_5"
    assert second.error == "boom"
    assert event["observed"] == {
        "target": "hr-db.find_approver",
        "status": CallStatus.BLOCKED,
        "stage": StageName.policy,
        "rule_id": "r1",
        "reason": "why",
        "call_id": "c_5",
        "http_status": 403,
    }
    assert event["trace"][0]["call_id"] == "c_5"
    assert event["explanation"] == "Attack stopped."
    assert AttackRunManager._scenario_event(second)["error"] == "boom"


def test_pending_scenario_event_has_empty_trace_and_no_explanation() -> None:
    view = AttackRunScenario.from_scenario(_scenario("a"))

    event = AttackRunManager._scenario_event(view)

    assert event["trace"] == []
    assert event["explanation"] is None
    assert event["error"] is None
    assert view.description == ""
