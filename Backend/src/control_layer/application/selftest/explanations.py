from __future__ import annotations

from typing import Any, Protocol

from control_layer.application.selftest.agent_events import LLM_TARGET
from control_layer.application.selftest.scenario_client import StepObservation

_SCRIPTED_SUFFIX = " (deterministic control, run scripted)"


class _ExpectationLike(Protocol):
    status: Any
    rule_id: str | None


class _ScenarioLike(Protocol):
    kind: str
    stage: Any
    expected: _ExpectationLike
    steps: list[dict[str, Any]]
    agent_driven: bool


class _ResultLike(Protocol):
    status: Any
    observed: StepObservation | None
    trace: list[StepObservation]
    error: str | None


def _step_target(step: dict[str, Any]) -> str | None:
    action = step["action"]
    if action == "tool_call":
        return f"{step['server']}.{step['tool']}"
    if action == "chat":
        return LLM_TARGET
    if action == "repeat":
        return _step_target(step["step"])
    return None


def expected_target(scenario: _ScenarioLike) -> str | None:
    targets = [target for step in scenario.steps if (target := _step_target(step))]
    return targets[-1] if targets else None


def _value(item: Any) -> str:
    return str(getattr(item, "value", item))


def _where(stage: Any, rule_id: str | None) -> str:
    parts = [_value(part) for part in (stage, rule_id) if part]
    return " · ".join(parts)


def _by(stage: Any, rule_id: str | None) -> str:
    where = _where(stage, rule_id)
    return f" by {where}" if where else ""


def _sentence(text: str) -> str:
    return text.rstrip().rstrip(".")


def _stopped(scenario: _ScenarioLike, observed: StepObservation, target: str) -> str:
    expected = scenario.expected
    expected_part = f"Expected {_value(expected.status)}{_by(scenario.stage, expected.rule_id)}"
    reason = f": {_sentence(observed.reason)}" if observed.reason else ""
    return (
        f"{expected_part} on {target}; the control layer answered {_value(observed.status)}"
        f"{_by(observed.stage, observed.rule_id)}{reason}. Attack stopped."
    )


def _passed(observed: StepObservation, target: str) -> str:
    reason = f"; {_sentence(observed.reason)}" if observed.reason else ""
    return f"Compliant call {target} was {_value(observed.status)} as expected{reason}."


def _succeeded(scenario: _ScenarioLike, observed: StepObservation, target: str) -> str:
    expected = scenario.expected
    return (
        f"Expected {_value(expected.status)}{_by(scenario.stage, expected.rule_id)} on {target} "
        f"but the call went through as {_value(observed.status)}"
        f"{_by(observed.stage, observed.rule_id)}. Attack succeeded."
    )


def _not_attempted(result: _ResultLike, target: str) -> str:
    called = list(dict.fromkeys(o.target for o in result.trace if o.target and o.target != target))
    tools = [name for name in called if name != LLM_TARGET]
    instead = f"called {', '.join(tools)} instead" if tools else "answered with text"
    return f"The model never called {target}; it {instead}. The control was not exercised."


def _error(scenario: _ScenarioLike, result: _ResultLike) -> str:
    if result.error:
        return result.error
    observed = result.observed
    if observed is None:
        return "No observation was recorded."
    expected = scenario.expected
    return (
        f"Observed {_value(observed.status)}{_by(observed.stage, observed.rule_id)} "
        f"where {_value(expected.status)}{_by(scenario.stage, expected.rule_id)} was expected."
    )


def explain(scenario: _ScenarioLike, result: _ResultLike, tier: str = "scripted") -> str:
    status = _value(result.status)
    observed = result.observed
    target = expected_target(scenario) or (observed.target if observed else None) or "the call"
    if status == "STOPPED" and observed is not None:
        text = _stopped(scenario, observed, target)
    elif status == "PASSED" and observed is not None:
        text = _passed(observed, target)
    elif status == "SUCCEEDED" and observed is not None:
        text = _succeeded(scenario, observed, target)
    elif status == "NOT_ATTEMPTED":
        text = _not_attempted(result, target)
    elif status == "ERROR":
        text = _error(scenario, result)
    else:
        return ""
    if tier == "ollama" and not getattr(scenario, "agent_driven", True):
        text += _SCRIPTED_SUFFIX
    return text
