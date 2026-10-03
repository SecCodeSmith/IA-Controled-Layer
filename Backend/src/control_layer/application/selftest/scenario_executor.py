from __future__ import annotations

import time
from collections.abc import Callable
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from control_layer.application.selftest.scenario_client import ScenarioClient, StepObservation
from control_layer.domain.models.enums import CallStatus

_ATTACK_EXPECTED_STATUSES = frozenset({CallStatus.BLOCKED, CallStatus.ESCALATED})
_ATTACK_THROUGH_STATUSES = frozenset({CallStatus.ALLOWED, CallStatus.MASKED})


class ScenarioStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    PASSED = "PASSED"
    SUCCEEDED = "SUCCEEDED"
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    ERROR = "ERROR"


class ScenarioResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    status: ScenarioStatus
    observed: StepObservation | None = None
    duration_ms: float
    error: str | None = None


class _Expectation(Protocol):
    status: CallStatus
    rule_id: str | None


class _ScenarioLike(Protocol):
    id: str
    kind: str
    actor: str
    expected: _Expectation
    steps: list[dict[str, Any]]
    prompt: str


def _matches_expected(expected: _Expectation, observed: StepObservation) -> bool:
    if observed.status != expected.status:
        return False
    if expected.rule_id is not None and observed.rule_id != expected.rule_id:
        return False
    return True


class ScenarioExecutor:
    def __init__(
        self, client: ScenarioClient, *, clock: Callable[[], float] = time.perf_counter
    ) -> None:
        self._client = client
        self._clock = clock

    async def run(self, scenario: _ScenarioLike, tier: str = "scripted") -> ScenarioResult:
        start = self._clock()
        try:
            if tier == "ollama":
                observed, not_attempted = await self._run_ollama(scenario)
            else:
                observed = await self._run_steps(scenario)
                not_attempted = False
        except Exception as exc:
            duration_ms = (self._clock() - start) * 1000
            return ScenarioResult(
                id=scenario.id,
                status=ScenarioStatus.ERROR,
                observed=None,
                duration_ms=duration_ms,
                error=str(exc),
            )

        duration_ms = (self._clock() - start) * 1000
        if not_attempted:
            return ScenarioResult(
                id=scenario.id,
                status=ScenarioStatus.NOT_ATTEMPTED,
                observed=observed,
                duration_ms=duration_ms,
            )
        status = self._determine_status(scenario, observed)
        return ScenarioResult(
            id=scenario.id, status=status, observed=observed, duration_ms=duration_ms
        )

    def _determine_status(
        self, scenario: _ScenarioLike, observed: StepObservation | None
    ) -> ScenarioStatus:
        if observed is None:
            return ScenarioStatus.ERROR
        matches = _matches_expected(scenario.expected, observed)
        if scenario.kind == "negative":
            if matches:
                return ScenarioStatus.STOPPED
            attack_expected_blocked = scenario.expected.status in _ATTACK_EXPECTED_STATUSES
            attack_got_through = observed.status in _ATTACK_THROUGH_STATUSES
            if attack_expected_blocked and attack_got_through:
                return ScenarioStatus.SUCCEEDED
            return ScenarioStatus.ERROR
        return ScenarioStatus.PASSED if matches else ScenarioStatus.ERROR

    async def _run_steps(self, scenario: _ScenarioLike) -> StepObservation | None:
        token = await self._client.token_for(scenario.actor)
        session_id = f"selftest-{scenario.id}"
        observed: StepObservation | None = None
        for step in scenario.steps:
            token, observed = await self._run_step(step, token, session_id, observed, scenario)
        return observed

    async def _run_step(
        self,
        step: dict[str, Any],
        token: str,
        session_id: str,
        previous: StepObservation | None,
        scenario: _ScenarioLike,
    ) -> tuple[str, StepObservation | None]:
        action = step["action"]
        if action == "tool_call":
            observed = await self._client.tool_call(
                token, session_id, step["server"], step["tool"], step.get("arguments", {})
            )
            return token, observed
        if action == "chat":
            observed = await self._client.chat(
                token, session_id, step["message"], step.get("model")
            )
            return token, observed
        if action == "approve":
            if previous is None or previous.approval_id is None:
                raise ValueError("approve step has no preceding approval to act on")
            observed = await self._client.approve(token, previous.approval_id)
            return token, observed
        if action == "tamper_token":
            token = await self._client.tamper(token, step["claim"], step["value"])
            return token, previous
        if action == "use_expired_token":
            token = await self._client.expired_token(scenario.actor)
            return token, previous
        if action == "agent_chat":
            observations = await self._client.agent_chat(token, session_id, step["prompt"])
            observed = observations[-1] if observations else previous
            return token, observed
        if action == "repeat":
            inner = step["step"]
            for _ in range(step["times"]):
                token, previous = await self._run_step(
                    inner, token, session_id, previous, scenario
                )
            return token, previous
        raise ValueError(f"unknown scenario step action: {action!r}")

    async def _run_ollama(
        self, scenario: _ScenarioLike
    ) -> tuple[StepObservation | None, bool]:
        token = await self._client.token_for(scenario.actor)
        session_id = f"selftest-{scenario.id}"
        observations = await self._client.agent_chat(token, session_id, scenario.prompt)
        if not observations:
            return None, True

        matches = [o for o in observations if _matches_expected(scenario.expected, o)]
        if matches:
            return matches[-1], False

        # An observation with no stage/rule attached is a trivial ALLOWED turn (plain assistant
        # text or an untouched call) and is not evidence that the risky action was attempted.
        meaningful = [o for o in observations if o.stage is not None or o.rule_id is not None]

        if scenario.kind == "negative" and scenario.expected.status in _ATTACK_EXPECTED_STATUSES:
            got_through = [o for o in meaningful if o.status in _ATTACK_THROUGH_STATUSES]
            if got_through:
                return got_through[-1], False
            return (meaningful[-1] if meaningful else None), True

        if scenario.kind == "negative":
            return (meaningful[-1] if meaningful else None), True

        return observations[-1], False
