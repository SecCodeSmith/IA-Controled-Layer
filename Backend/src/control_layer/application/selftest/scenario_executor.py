from __future__ import annotations

import time
from collections.abc import Callable
from enum import StrEnum
from typing import Any, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from control_layer.application.selftest.explanations import expected_target, explain
from control_layer.application.selftest.scenario_client import ScenarioClient, StepObservation
from control_layer.domain.models.enums import CallStatus

_ATTACK_EXPECTED_STATUSES = frozenset({CallStatus.BLOCKED, CallStatus.ESCALATED})
_ATTACK_THROUGH_STATUSES = frozenset({CallStatus.ALLOWED, CallStatus.MASKED})
_MASK_STOPPING_STATUSES = frozenset(
    {CallStatus.FLAGGED, CallStatus.MASKED, CallStatus.BLOCKED, CallStatus.ESCALATED}
)
_DENIED_STATUSES = _MASK_STOPPING_STATUSES


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
    via: Literal["agent", "scripted"] = "scripted"
    error: str | None = None
    trace: list[StepObservation] = Field(default_factory=list)
    explanation: str = ""


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
    stage: Any
    agent_driven: bool


def _matches_expected(expected: _Expectation, observed: StepObservation) -> bool:
    if observed.status != expected.status:
        return False
    return expected.rule_id is None or observed.rule_id == expected.rule_id


def _varied(step: dict[str, Any], vary: str | None, index: int) -> dict[str, Any]:
    if vary is None:
        return step
    arguments = dict(step.get("arguments", {}))
    arguments[vary] = f"{arguments.get(vary, '')}-{index}"
    return {**step, "arguments": arguments}


def _judge_negative(expected: _Expectation, attempt: StepObservation) -> ScenarioStatus:
    stopping = (
        _ATTACK_EXPECTED_STATUSES
        if expected.status in _ATTACK_EXPECTED_STATUSES
        else _MASK_STOPPING_STATUSES
    )
    return ScenarioStatus.STOPPED if attempt.status in stopping else ScenarioStatus.SUCCEEDED


def _informative(observations: list[StepObservation]) -> StepObservation | None:
    denied = [o for o in observations if o.status in _DENIED_STATUSES]
    if denied:
        return denied[-1]
    return observations[-1] if observations else None


class _Outcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: ScenarioStatus
    observed: StepObservation | None
    via: Literal["agent", "scripted"]


class ScenarioExecutor:
    def __init__(
        self,
        client: ScenarioClient,
        *,
        clock: Callable[[], float] = time.perf_counter,
        run_token: str | None = None,
    ) -> None:
        self._client = client
        self._clock = clock
        self._run_token = run_token or uuid4().hex[:8]

    def _session_for(self, scenario: _ScenarioLike) -> str:
        return f"selftest-{scenario.id}-{self._run_token}"

    async def run(self, scenario: _ScenarioLike, tier: str = "scripted") -> ScenarioResult:
        start = self._clock()
        via: Literal["agent", "scripted"] = (
            "agent"
            if tier == "ollama" and getattr(scenario, "agent_driven", True)
            else "scripted"
        )
        trace: list[StepObservation] = []
        try:
            outcome = await (
                self._run_agent(scenario, trace)
                if via == "agent"
                else self._run_scripted(scenario, trace)
            )
        except Exception as exc:
            return self._finish(
                scenario, tier, start, trace,
                _Outcome(status=ScenarioStatus.ERROR, observed=None, via=via), str(exc),
            )
        return self._finish(scenario, tier, start, trace, outcome)

    def _finish(
        self,
        scenario: _ScenarioLike,
        tier: str,
        start: float,
        trace: list[StepObservation],
        outcome: _Outcome,
        error: str | None = None,
    ) -> ScenarioResult:
        result = ScenarioResult(
            id=scenario.id,
            status=outcome.status,
            observed=outcome.observed,
            duration_ms=(self._clock() - start) * 1000,
            via=outcome.via,
            error=error,
            trace=list(trace),
        )
        return result.model_copy(update={"explanation": explain(scenario, result, tier)})

    async def _run_scripted(
        self, scenario: _ScenarioLike, trace: list[StepObservation]
    ) -> _Outcome:
        observed = await self._run_steps(scenario, trace)
        return _Outcome(
            status=self._determine_status(scenario, observed), observed=observed, via="scripted"
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

    async def _run_steps(
        self, scenario: _ScenarioLike, trace: list[StepObservation]
    ) -> StepObservation | None:
        token = await self._client.token_for(scenario.actor)
        session_id = self._session_for(scenario)
        observed: StepObservation | None = None
        for step in scenario.steps:
            token, observed = await self._run_step(
                step, token, session_id, observed, scenario, trace
            )
        return observed

    async def _run_step(
        self,
        step: dict[str, Any],
        token: str,
        session_id: str,
        previous: StepObservation | None,
        scenario: _ScenarioLike,
        trace: list[StepObservation],
    ) -> tuple[str, StepObservation | None]:
        action = step["action"]
        if action == "tool_call":
            observed = await self._client.tool_call(
                token, session_id, step["server"], step["tool"], step.get("arguments", {})
            )
            trace.append(observed)
            return token, observed
        if action == "chat":
            observed = await self._client.chat(
                token, session_id, step["message"], step.get("model"), step.get("max_tokens")
            )
            trace.append(observed)
            return token, observed
        if action == "approve":
            if previous is None or previous.approval_id is None:
                raise ValueError("approve step has no preceding approval to act on")
            observed = await self._client.approve(token, previous.approval_id)
            trace.append(observed)
            return token, observed
        if action == "tamper_token":
            token = await self._client.tamper(token, step["claim"], step["value"])
            return token, previous
        if action == "use_expired_token":
            token = await self._client.expired_token(scenario.actor)
            return token, previous
        if action == "agent_chat":
            observations = await self._client.agent_chat(token, session_id, step["prompt"])
            trace.extend(observations)
            observed = observations[-1] if observations else previous
            return token, observed
        if action == "repeat":
            for index in range(step["times"]):
                inner = _varied(step["step"], step.get("vary"), index)
                token, previous = await self._run_step(
                    inner, token, session_id, previous, scenario, trace
                )
            return token, previous
        raise ValueError(f"unknown scenario step action: {action!r}")

    async def _run_agent(
        self, scenario: _ScenarioLike, trace: list[StepObservation]
    ) -> _Outcome:
        token = await self._client.token_for(scenario.actor)
        session_id = self._session_for(scenario)
        observations = await self._client.agent_chat(token, session_id, scenario.prompt)
        trace.extend(observations)
        target = expected_target(scenario)
        attempts = [o for o in observations if o.target == target]
        if not attempts:
            others = [o for o in observations if o.target != target]
            return _Outcome(
                status=ScenarioStatus.NOT_ATTEMPTED, observed=_informative(others), via="agent"
            )
        attempt = await self._settle_approval(scenario, token, attempts[-1])
        if attempt is not attempts[-1]:
            trace.append(attempt)
        return _Outcome(
            status=self._judge_attempt(scenario, attempt), observed=attempt, via="agent"
        )

    async def _settle_approval(
        self, scenario: _ScenarioLike, token: str, attempt: StepObservation
    ) -> StepObservation:
        wants_approval = any(step["action"] == "approve" for step in scenario.steps)
        if not (
            scenario.kind == "positive"
            and wants_approval
            and attempt.status == CallStatus.ESCALATED
            and attempt.approval_id is not None
        ):
            return attempt
        approved = await self._client.approve(token, attempt.approval_id)
        if approved.target is None:
            approved = approved.model_copy(update={"target": attempt.target})
        return approved

    @staticmethod
    def _judge_attempt(scenario: _ScenarioLike, attempt: StepObservation) -> ScenarioStatus:
        if scenario.kind == "negative":
            return _judge_negative(scenario.expected, attempt)
        matches = _matches_expected(scenario.expected, attempt)
        return ScenarioStatus.PASSED if matches else ScenarioStatus.ERROR
