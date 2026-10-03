from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, Field

from control_layer.application.selftest.scenario_client import StepObservation
from control_layer.application.selftest.scenario_executor import ScenarioExecutor, ScenarioStatus
from control_layer.domain.models.enums import CallStatus, StageName


class _Expectation(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: CallStatus
    rule_id: str | None = None


class _Scenario(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str = "scenario"
    kind: str
    actor: str = "anna.kowalska"
    stage: StageName = StageName.policy
    expected: _Expectation
    owasp: list[str] = Field(default_factory=list)
    steps: list[dict[str, Any]] = Field(default_factory=list)
    prompt: str = "do the thing"


def _obs(
    status: CallStatus,
    *,
    stage: StageName | None = None,
    rule_id: str | None = None,
    approval_id: str | None = None,
    http_status: int = 200,
) -> StepObservation:
    return StepObservation(
        http_status=http_status, status=status, stage=stage, rule_id=rule_id,
        approval_id=approval_id,
    )


class FakeScenarioClient:
    def __init__(self) -> None:
        self.tool_calls: list[tuple[str, str, str, str, dict]] = []
        self.chats: list[tuple[str, str, str, str | None]] = []
        self.approvals: list[tuple[str, str]] = []
        self.tampers: list[tuple[str, str, object]] = []
        self.expired_calls: list[str] = []
        self.tool_call_results: list[StepObservation] = list()
        self.chat_result: StepObservation | None = None
        self.approve_result: StepObservation | None = None
        self.agent_chat_result: list[StepObservation] = []
        self.raise_on: str | None = None

    async def token_for(self, sub: str) -> str:
        return f"token:{sub}"

    async def tamper(self, token: str, claim: str, value: object) -> str:
        self.tampers.append((token, claim, value))
        return f"{token}:tampered:{claim}={value}"

    async def expired_token(self, sub: str) -> str:
        self.expired_calls.append(sub)
        return f"expired:{sub}"

    async def chat(
        self, token: str, session_id: str, message: str, model: str | None = None
    ) -> StepObservation:
        if self.raise_on == "chat":
            raise RuntimeError("boom")
        self.chats.append((token, session_id, message, model))
        return self.chat_result or _obs(CallStatus.ALLOWED)

    async def tool_call(
        self, token: str, session_id: str, server: str, tool: str, arguments: dict
    ) -> StepObservation:
        if self.raise_on == "tool_call":
            raise RuntimeError("boom")
        self.tool_calls.append((token, session_id, server, tool, arguments))
        if self.tool_call_results:
            return self.tool_call_results[min(len(self.tool_calls) - 1, len(self.tool_call_results) - 1)]
        return _obs(CallStatus.ALLOWED)

    async def approve(self, token: str, approval_id: str) -> StepObservation:
        self.approvals.append((token, approval_id))
        return self.approve_result or _obs(CallStatus.ALLOWED)

    async def agent_chat(
        self, token: str, session_id: str, prompt: str
    ) -> list[StepObservation]:
        return self.agent_chat_result


async def test_negative_scenario_is_stopped_when_status_and_rule_match() -> None:
    client = FakeScenarioClient()
    client.tool_call_results = [_obs(CallStatus.BLOCKED, stage=StageName.authorization, rule_id="role_provisioning")]
    scenario = _Scenario(
        id="s1", kind="negative",
        expected=_Expectation(status=CallStatus.BLOCKED, rule_id="role_provisioning"),
        steps=[{"action": "tool_call", "server": "hr-db", "tool": "find_approver", "arguments": {}}],
    )
    executor = ScenarioExecutor(client)

    result = await executor.run(scenario)

    assert result.status == ScenarioStatus.STOPPED
    assert result.observed is not None
    assert result.observed.rule_id == "role_provisioning"
    assert result.duration_ms >= 0


async def test_negative_scenario_stopped_when_expected_rule_is_none() -> None:
    client = FakeScenarioClient()
    client.chat_result = _obs(CallStatus.BLOCKED, rule_id="model_allowlist")
    scenario = _Scenario(
        id="s2", kind="negative",
        expected=_Expectation(status=CallStatus.BLOCKED, rule_id=None),
        steps=[{"action": "chat", "message": "hello", "model": "gpt-4"}],
    )
    executor = ScenarioExecutor(client)

    result = await executor.run(scenario)

    assert result.status == ScenarioStatus.STOPPED


async def test_negative_scenario_is_succeeded_when_attack_got_through() -> None:
    client = FakeScenarioClient()
    client.tool_call_results = [_obs(CallStatus.ALLOWED)]
    scenario = _Scenario(
        id="s3", kind="negative",
        expected=_Expectation(status=CallStatus.BLOCKED, rule_id="role_provisioning"),
        steps=[{"action": "tool_call", "server": "hr-db", "tool": "find_approver", "arguments": {}}],
    )
    executor = ScenarioExecutor(client)

    result = await executor.run(scenario)

    assert result.status == ScenarioStatus.SUCCEEDED


async def test_negative_scenario_mismatch_without_bypass_is_error() -> None:
    client = FakeScenarioClient()
    client.tool_call_results = [_obs(CallStatus.ESCALATED, rule_id="other_rule")]
    scenario = _Scenario(
        id="s4", kind="negative",
        expected=_Expectation(status=CallStatus.BLOCKED, rule_id="role_provisioning"),
        steps=[{"action": "tool_call", "server": "hr-db", "tool": "find_approver", "arguments": {}}],
    )
    executor = ScenarioExecutor(client)

    result = await executor.run(scenario)

    assert result.status == ScenarioStatus.ERROR


async def test_positive_scenario_is_passed_when_matching() -> None:
    client = FakeScenarioClient()
    client.tool_call_results = [_obs(CallStatus.ALLOWED)]
    scenario = _Scenario(
        id="s5", kind="positive",
        expected=_Expectation(status=CallStatus.ALLOWED),
        steps=[{"action": "tool_call", "server": "ci", "tool": "get_run", "arguments": {}}],
    )
    executor = ScenarioExecutor(client)

    result = await executor.run(scenario)

    assert result.status == ScenarioStatus.PASSED


async def test_positive_scenario_mismatch_is_error() -> None:
    client = FakeScenarioClient()
    client.tool_call_results = [_obs(CallStatus.BLOCKED, rule_id="role_provisioning")]
    scenario = _Scenario(
        id="s6", kind="positive",
        expected=_Expectation(status=CallStatus.ALLOWED),
        steps=[{"action": "tool_call", "server": "ci", "tool": "get_run", "arguments": {}}],
    )
    executor = ScenarioExecutor(client)

    result = await executor.run(scenario)

    assert result.status == ScenarioStatus.ERROR


async def test_exception_from_client_is_reported_as_error() -> None:
    client = FakeScenarioClient()
    client.raise_on = "tool_call"
    scenario = _Scenario(
        id="s7", kind="negative",
        expected=_Expectation(status=CallStatus.BLOCKED),
        steps=[{"action": "tool_call", "server": "ci", "tool": "get_run", "arguments": {}}],
    )
    executor = ScenarioExecutor(client)

    result = await executor.run(scenario)

    assert result.status == ScenarioStatus.ERROR
    assert result.error == "boom"
    assert result.observed is None


async def test_repeat_runs_the_inner_step_n_times_and_uses_last_observation() -> None:
    client = FakeScenarioClient()
    client.tool_call_results = [
        _obs(CallStatus.ALLOWED),
        _obs(CallStatus.ALLOWED),
        _obs(CallStatus.BLOCKED, rule_id="loop_guard"),
    ]
    scenario = _Scenario(
        id="s8", kind="negative",
        expected=_Expectation(status=CallStatus.BLOCKED, rule_id="loop_guard"),
        steps=[
            {
                "action": "repeat",
                "times": 3,
                "step": {
                    "action": "tool_call",
                    "server": "ci",
                    "tool": "get_run",
                    "arguments": {},
                },
            }
        ],
    )
    executor = ScenarioExecutor(client)

    result = await executor.run(scenario)

    assert len(client.tool_calls) == 3
    assert result.status == ScenarioStatus.STOPPED
    assert result.observed is not None
    assert result.observed.rule_id == "loop_guard"


async def test_approve_step_uses_approval_id_from_previous_observation() -> None:
    client = FakeScenarioClient()
    client.tool_call_results = [
        _obs(CallStatus.ESCALATED, rule_id="destructive_requires_approval", approval_id="ap_1")
    ]
    client.approve_result = _obs(CallStatus.ESCALATED, rule_id="destructive_requires_approval")
    scenario = _Scenario(
        id="s9", kind="positive",
        expected=_Expectation(status=CallStatus.ESCALATED, rule_id="destructive_requires_approval"),
        steps=[
            {"action": "tool_call", "server": "github", "tool": "delete_branch", "arguments": {}},
            {"action": "approve"},
        ],
    )
    executor = ScenarioExecutor(client)

    result = await executor.run(scenario)

    assert client.approvals == [("token:anna.kowalska", "ap_1")]
    assert result.status == ScenarioStatus.PASSED


async def test_tamper_token_changes_the_token_used_by_the_next_step() -> None:
    client = FakeScenarioClient()
    client.tool_call_results = [_obs(CallStatus.BLOCKED)]
    scenario = _Scenario(
        id="s10", kind="negative",
        expected=_Expectation(status=CallStatus.BLOCKED),
        steps=[
            {"action": "tamper_token", "claim": "role", "value": "finance"},
            {"action": "tool_call", "server": "payments", "tool": "get_balance", "arguments": {}},
        ],
    )
    executor = ScenarioExecutor(client)

    await executor.run(scenario)

    assert client.tampers == [("token:anna.kowalska", "role", "finance")]
    assert client.tool_calls[0][0] == "token:anna.kowalska:tampered:role=finance"


async def test_use_expired_token_changes_the_token_used_by_the_next_step() -> None:
    client = FakeScenarioClient()
    client.tool_call_results = [_obs(CallStatus.BLOCKED)]
    scenario = _Scenario(
        id="s11", kind="negative",
        expected=_Expectation(status=CallStatus.BLOCKED),
        steps=[
            {"action": "use_expired_token"},
            {"action": "tool_call", "server": "ci", "tool": "get_run", "arguments": {}},
        ],
    )
    executor = ScenarioExecutor(client)

    await executor.run(scenario)

    assert client.expired_calls == ["anna.kowalska"]
    assert client.tool_calls[0][0] == "expired:anna.kowalska"


async def test_ollama_tier_not_attempted_when_no_observations() -> None:
    client = FakeScenarioClient()
    client.agent_chat_result = []
    scenario = _Scenario(
        id="s12", kind="negative",
        expected=_Expectation(status=CallStatus.BLOCKED, rule_id="role_provisioning"),
        steps=[{"action": "tool_call", "server": "hr-db", "tool": "find_approver", "arguments": {}}],
    )
    executor = ScenarioExecutor(client)

    result = await executor.run(scenario, tier="ollama")

    assert result.status == ScenarioStatus.NOT_ATTEMPTED


async def test_ollama_tier_not_attempted_when_model_never_tries_the_risky_action() -> None:
    client = FakeScenarioClient()
    client.agent_chat_result = [_obs(CallStatus.ALLOWED, stage=None, rule_id=None)]
    scenario = _Scenario(
        id="s13", kind="negative",
        expected=_Expectation(status=CallStatus.BLOCKED, rule_id="role_provisioning"),
        steps=[{"action": "tool_call", "server": "hr-db", "tool": "find_approver", "arguments": {}}],
    )
    executor = ScenarioExecutor(client)

    result = await executor.run(scenario, tier="ollama")

    assert result.status == ScenarioStatus.NOT_ATTEMPTED


async def test_ollama_tier_succeeded_when_attack_got_through() -> None:
    client = FakeScenarioClient()
    client.agent_chat_result = [_obs(CallStatus.ALLOWED, stage=StageName.authorization, rule_id="role_provisioning")]
    scenario = _Scenario(
        id="s14", kind="negative",
        expected=_Expectation(status=CallStatus.BLOCKED, rule_id="role_provisioning"),
        steps=[{"action": "tool_call", "server": "hr-db", "tool": "find_approver", "arguments": {}}],
    )
    executor = ScenarioExecutor(client)

    result = await executor.run(scenario, tier="ollama")

    assert result.status == ScenarioStatus.SUCCEEDED


async def test_ollama_tier_stopped_when_a_matching_observation_exists() -> None:
    client = FakeScenarioClient()
    client.agent_chat_result = [
        _obs(CallStatus.ALLOWED),
        _obs(CallStatus.BLOCKED, stage=StageName.authorization, rule_id="role_provisioning"),
    ]
    scenario = _Scenario(
        id="s15", kind="negative",
        expected=_Expectation(status=CallStatus.BLOCKED, rule_id="role_provisioning"),
        steps=[{"action": "tool_call", "server": "hr-db", "tool": "find_approver", "arguments": {}}],
    )
    executor = ScenarioExecutor(client)

    result = await executor.run(scenario, tier="ollama")

    assert result.status == ScenarioStatus.STOPPED
    assert result.observed is not None
    assert result.observed.rule_id == "role_provisioning"
