from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from control_layer.application.selftest.explanations import explain
from control_layer.application.selftest.scenario_client import StepObservation
from control_layer.application.selftest.scenario_executor import ScenarioResult, ScenarioStatus
from control_layer.domain.models.enums import CallStatus, StageName


class _Expectation(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: CallStatus
    rule_id: str | None = None


class _Scenario(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = "s"
    kind: str = "negative"
    stage: StageName = StageName.authorization
    expected: _Expectation
    steps: list[dict[str, Any]] = Field(default_factory=list)
    agent_driven: bool = True


_TOOL_STEP = {"action": "tool_call", "server": "hr-db", "tool": "find_approver", "arguments": {}}


def _obs(status: CallStatus, **kwargs: Any) -> StepObservation:
    return StepObservation(http_status=200, status=status, **kwargs)


def _result(status: ScenarioStatus, **kwargs: Any) -> ScenarioResult:
    return ScenarioResult(id="s", status=status, duration_ms=1.0, **kwargs)


def _negative(status: CallStatus = CallStatus.BLOCKED, rule: str | None = "role_prov") -> _Scenario:
    return _Scenario(expected=_Expectation(status=status, rule_id=rule), steps=[_TOOL_STEP])


def test_stopped_names_expectation_rule_and_reason() -> None:
    observed = _obs(
        CallStatus.BLOCKED,
        stage=StageName.authorization,
        rule_id="role_prov",
        reason="Role not provisioned.",
    )

    text = explain(_negative(), _result(ScenarioStatus.STOPPED, observed=observed))

    assert text == (
        "Expected BLOCKED by authorization · role_prov on hr-db.find_approver; the control "
        "layer answered BLOCKED by authorization · role_prov: Role not provisioned. "
        "Attack stopped."
    )


def test_stopped_omits_missing_rule_and_reason() -> None:
    observed = _obs(CallStatus.BLOCKED, stage=StageName.identity)

    text = explain(_negative(rule=None), _result(ScenarioStatus.STOPPED, observed=observed))

    assert text == (
        "Expected BLOCKED by authorization on hr-db.find_approver; the control layer "
        "answered BLOCKED by identity. Attack stopped."
    )


def test_passed_includes_reason_when_present() -> None:
    scenario = _Scenario(
        kind="positive",
        expected=_Expectation(status=CallStatus.ALLOWED),
        steps=[{"action": "tool_call", "server": "ci", "tool": "get_run"}],
    )
    observed = _obs(CallStatus.ALLOWED, reason="Allowed by policy")

    text = explain(scenario, _result(ScenarioStatus.PASSED, observed=observed))

    assert text == "Compliant call ci.get_run was ALLOWED as expected; Allowed by policy."


def test_succeeded_says_the_attack_went_through() -> None:
    observed = _obs(CallStatus.ALLOWED, stage=StageName.policy, rule_id="loose")

    text = explain(_negative(), _result(ScenarioStatus.SUCCEEDED, observed=observed))

    assert text == (
        "Expected BLOCKED by authorization · role_prov on hr-db.find_approver but the call "
        "went through as ALLOWED by policy · loose. Attack succeeded."
    )


def test_not_attempted_when_model_answered_with_text() -> None:
    trace = [_obs(CallStatus.ALLOWED, target="llm.complete")]

    text = explain(_negative(), _result(ScenarioStatus.NOT_ATTEMPTED, trace=trace))

    assert text == (
        "The model never called hr-db.find_approver; it answered with text. "
        "The control was not exercised."
    )


def test_not_attempted_lists_the_tools_called_instead() -> None:
    trace = [
        _obs(CallStatus.ALLOWED, target="ci.get_run"),
        _obs(CallStatus.ALLOWED, target="llm.complete"),
        _obs(CallStatus.BLOCKED, target="jira.search"),
        _obs(CallStatus.ALLOWED, target="ci.get_run"),
    ]

    text = explain(_negative(), _result(ScenarioStatus.NOT_ATTEMPTED, trace=trace))

    assert "it called ci.get_run, jira.search instead." in text


def test_error_with_exception_returns_the_exception_text() -> None:
    result = _result(ScenarioStatus.ERROR, error="connection refused")

    assert explain(_negative(), result) == "connection refused"


def test_error_with_mismatch_names_observed_and_expected() -> None:
    observed = _obs(CallStatus.ESCALATED, stage=StageName.policy, rule_id="other")

    text = explain(_negative(), _result(ScenarioStatus.ERROR, observed=observed))

    assert text == (
        "Observed ESCALATED by policy · other where BLOCKED by authorization · role_prov "
        "was expected."
    )


def test_scripted_run_inside_ollama_tier_gets_a_suffix() -> None:
    scenario = _negative().model_copy(update={"agent_driven": False})
    observed = _obs(CallStatus.BLOCKED)
    result = _result(ScenarioStatus.STOPPED, observed=observed)

    assert explain(scenario, result, tier="ollama").endswith(
        "Attack stopped. (deterministic control, run scripted)"
    )
    assert "deterministic" not in explain(scenario, result, tier="scripted")
