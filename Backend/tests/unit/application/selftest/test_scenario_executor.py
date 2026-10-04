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
    agent_driven: bool = True


_FIND_APPROVER_STEP = {
    "action": "tool_call",
    "server": "hr-db",
    "tool": "find_approver",
    "arguments": {},
}


def _obs(
    status: CallStatus,
    *,
    stage: StageName | None = None,
    rule_id: str | None = None,
    approval_id: str | None = None,
    http_status: int = 200,
    target: str | None = None,
    call_id: str | None = None,
) -> StepObservation:
    return StepObservation(
        http_status=http_status,
        status=status,
        stage=stage,
        rule_id=rule_id,
        approval_id=approval_id,
        target=target,
        call_id=call_id,
    )


class FakeScenarioClient:
    def __init__(self) -> None:
        self.tool_calls: list[tuple[str, str, str, str, dict]] = []
        self.chats: list[tuple[str, str, str, str | None]] = []
        self.chat_max_tokens: list[int | None] = []
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
        self,
        token: str,
        session_id: str,
        message: str,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> StepObservation:
        self.chat_max_tokens.append(max_tokens)
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
            index = min(len(self.tool_calls) - 1, len(self.tool_call_results) - 1)
            return self.tool_call_results[index]
        return _obs(CallStatus.ALLOWED)

    async def approve(self, token: str, approval_id: str) -> StepObservation:
        self.approvals.append((token, approval_id))
        return self.approve_result or _obs(CallStatus.ALLOWED)

    async def agent_chat(self, token: str, session_id: str, prompt: str) -> list[StepObservation]:
        return self.agent_chat_result


async def test_negative_scenario_is_stopped_when_status_and_rule_match() -> None:
    client = FakeScenarioClient()
    client.tool_call_results = [
        _obs(CallStatus.BLOCKED, stage=StageName.authorization, rule_id="role_provisioning")
    ]
    scenario = _Scenario(
        id="s1",
        kind="negative",
        expected=_Expectation(status=CallStatus.BLOCKED, rule_id="role_provisioning"),
        steps=[_FIND_APPROVER_STEP],
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
        id="s2",
        kind="negative",
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
        id="s3",
        kind="negative",
        expected=_Expectation(status=CallStatus.BLOCKED, rule_id="role_provisioning"),
        steps=[_FIND_APPROVER_STEP],
    )
    executor = ScenarioExecutor(client)

    result = await executor.run(scenario)

    assert result.status == ScenarioStatus.SUCCEEDED


async def test_negative_scenario_mismatch_without_bypass_is_error() -> None:
    client = FakeScenarioClient()
    client.tool_call_results = [_obs(CallStatus.ESCALATED, rule_id="other_rule")]
    scenario = _Scenario(
        id="s4",
        kind="negative",
        expected=_Expectation(status=CallStatus.BLOCKED, rule_id="role_provisioning"),
        steps=[_FIND_APPROVER_STEP],
    )
    executor = ScenarioExecutor(client)

    result = await executor.run(scenario)

    assert result.status == ScenarioStatus.ERROR


async def test_positive_scenario_is_passed_when_matching() -> None:
    client = FakeScenarioClient()
    client.tool_call_results = [_obs(CallStatus.ALLOWED)]
    scenario = _Scenario(
        id="s5",
        kind="positive",
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
        id="s6",
        kind="positive",
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
        id="s7",
        kind="negative",
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
        id="s8",
        kind="negative",
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
        id="s9",
        kind="positive",
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
        id="s10",
        kind="negative",
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
        id="s11",
        kind="negative",
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


_HR_TARGET = "hr-db.find_approver"
_HR_BLOCK = {"stage": StageName.authorization, "rule_id": "role_provisioning"}


def _negative_hr(expected: CallStatus = CallStatus.BLOCKED) -> _Scenario:
    return _Scenario(
        id="neg",
        kind="negative",
        expected=_Expectation(status=expected, rule_id="role_provisioning"),
        steps=[_FIND_APPROVER_STEP],
    )


def _positive_ci() -> _Scenario:
    return _Scenario(
        id="pos",
        kind="positive",
        expected=_Expectation(status=CallStatus.ALLOWED),
        steps=[{"action": "tool_call", "server": "ci", "tool": "get_run", "arguments": {}}],
    )


def _masked_logs() -> _Scenario:
    return _Scenario(
        id="mask",
        kind="negative",
        expected=_Expectation(status=CallStatus.MASKED, rule_id="pii_masking"),
        steps=[{"action": "tool_call", "server": "logs-db", "tool": "query", "arguments": {}}],
    )


async def test_ollama_tier_not_attempted_when_no_observations() -> None:
    client = FakeScenarioClient()

    result = await ScenarioExecutor(client).run(_negative_hr(), tier="ollama")

    assert result.status == ScenarioStatus.NOT_ATTEMPTED
    assert result.observed is None
    assert result.via == "agent"


async def test_ollama_tier_not_attempted_when_model_only_chats() -> None:
    client = FakeScenarioClient()
    client.agent_chat_result = [_obs(CallStatus.ALLOWED, target="llm.complete")]

    result = await ScenarioExecutor(client).run(_negative_hr(), tier="ollama")

    assert result.status == ScenarioStatus.NOT_ATTEMPTED
    assert result.observed is not None
    assert result.observed.target == "llm.complete"


async def test_ollama_not_attempted_reports_blocked_observation_on_other_target() -> None:
    client = FakeScenarioClient()
    client.agent_chat_result = [
        _obs(CallStatus.ALLOWED, target="llm.complete"),
        _obs(CallStatus.BLOCKED, rule_id="other", target="payments.get_balance"),
        _obs(CallStatus.ALLOWED, target="llm.complete"),
    ]

    result = await ScenarioExecutor(client).run(_negative_hr(), tier="ollama")

    assert result.status == ScenarioStatus.NOT_ATTEMPTED
    assert result.observed is not None
    assert result.observed.rule_id == "other"


async def test_ollama_positive_chat_only_model_is_not_attempted() -> None:
    client = FakeScenarioClient()
    client.agent_chat_result = [_obs(CallStatus.ALLOWED, target="llm.complete")]

    result = await ScenarioExecutor(client).run(_positive_ci(), tier="ollama")

    assert result.status == ScenarioStatus.NOT_ATTEMPTED


async def test_ollama_positive_with_attempt_passes() -> None:
    client = FakeScenarioClient()
    client.agent_chat_result = [
        _obs(CallStatus.ALLOWED, target="ci.get_run"),
        _obs(CallStatus.ALLOWED, target="llm.complete"),
    ]

    result = await ScenarioExecutor(client).run(_positive_ci(), tier="ollama")

    assert result.status == ScenarioStatus.PASSED
    assert result.observed is not None
    assert result.observed.target == "ci.get_run"


async def test_ollama_positive_attempt_with_wrong_status_is_error() -> None:
    client = FakeScenarioClient()
    client.agent_chat_result = [_obs(CallStatus.BLOCKED, rule_id="x", target="ci.get_run")]

    result = await ScenarioExecutor(client).run(_positive_ci(), tier="ollama")

    assert result.status == ScenarioStatus.ERROR


async def test_ollama_positive_approval_flow_approves_and_judges_the_result() -> None:
    client = FakeScenarioClient()
    client.agent_chat_result = [
        _obs(
            CallStatus.ESCALATED,
            rule_id="destructive_requires_approval",
            approval_id="ap_7",
            target="github.delete_branch",
        )
    ]
    client.approve_result = _obs(CallStatus.ESCALATED, rule_id="destructive_requires_approval")
    scenario = _Scenario(
        id="appr",
        kind="positive",
        expected=_Expectation(status=CallStatus.ESCALATED, rule_id="destructive_requires_approval"),
        steps=[
            {"action": "tool_call", "server": "github", "tool": "delete_branch", "arguments": {}},
            {"action": "approve"},
        ],
    )

    result = await ScenarioExecutor(client).run(scenario, tier="ollama")

    assert client.approvals == [("token:anna.kowalska", "ap_7")]
    assert result.status == ScenarioStatus.PASSED
    assert result.via == "agent"


async def test_ollama_negative_stopped_by_a_different_rule() -> None:
    client = FakeScenarioClient()
    client.agent_chat_result = [
        _obs(CallStatus.ESCALATED, rule_id="another_rule", target=_HR_TARGET)
    ]

    result = await ScenarioExecutor(client).run(_negative_hr(), tier="ollama")

    assert result.status == ScenarioStatus.STOPPED
    assert result.observed is not None
    assert result.observed.rule_id == "another_rule"


async def test_ollama_negative_succeeded_when_attack_got_through() -> None:
    client = FakeScenarioClient()
    client.agent_chat_result = [_obs(CallStatus.ALLOWED, target=_HR_TARGET, **_HR_BLOCK)]

    result = await ScenarioExecutor(client).run(_negative_hr(), tier="ollama")

    assert result.status == ScenarioStatus.SUCCEEDED


async def test_ollama_negative_flagged_attempt_counts_as_succeeded() -> None:
    client = FakeScenarioClient()
    client.agent_chat_result = [_obs(CallStatus.FLAGGED, target=_HR_TARGET)]

    result = await ScenarioExecutor(client).run(_negative_hr(), tier="ollama")

    assert result.status == ScenarioStatus.SUCCEEDED


async def test_ollama_negative_stopped_when_matching_attempt_exists() -> None:
    client = FakeScenarioClient()
    client.agent_chat_result = [
        _obs(CallStatus.ALLOWED, target="llm.complete"),
        _obs(CallStatus.BLOCKED, target=_HR_TARGET, **_HR_BLOCK),
    ]

    result = await ScenarioExecutor(client).run(_negative_hr(), tier="ollama")

    assert result.status == ScenarioStatus.STOPPED
    assert result.observed is not None
    assert result.observed.rule_id == "role_provisioning"


async def test_ollama_masked_expected_but_allowed_is_succeeded() -> None:
    client = FakeScenarioClient()
    client.agent_chat_result = [_obs(CallStatus.ALLOWED, target="logs-db.query")]

    result = await ScenarioExecutor(client).run(_masked_logs(), tier="ollama")

    assert result.status == ScenarioStatus.SUCCEEDED


@pytest.mark.parametrize("status", [CallStatus.MASKED, CallStatus.BLOCKED, CallStatus.ESCALATED])
async def test_ollama_masked_expected_stopped_by_mask_or_stronger(status: CallStatus) -> None:
    client = FakeScenarioClient()
    client.agent_chat_result = [_obs(status, target="logs-db.query")]

    result = await ScenarioExecutor(client).run(_masked_logs(), tier="ollama")

    assert result.status == ScenarioStatus.STOPPED


async def test_non_agent_driven_scenario_runs_scripted_steps_in_ollama_tier() -> None:
    client = FakeScenarioClient()
    client.chat_result = _obs(CallStatus.BLOCKED, rule_id="model_allowlist")
    scenario = _Scenario(
        id="det",
        kind="negative",
        expected=_Expectation(status=CallStatus.BLOCKED, rule_id="model_allowlist"),
        steps=[{"action": "chat", "message": "hello", "model": "gpt-4"}],
        agent_driven=False,
    )

    result = await ScenarioExecutor(client).run(scenario, tier="ollama")

    assert result.status == ScenarioStatus.STOPPED
    assert result.via == "scripted"
    assert len(client.chats) == 1


async def test_scripted_tier_reports_via_scripted() -> None:
    client = FakeScenarioClient()

    result = await ScenarioExecutor(client).run(_positive_ci())

    assert result.via == "scripted"


async def test_repeat_vary_suffixes_the_argument_with_the_iteration_index() -> None:
    client = FakeScenarioClient()
    scenario = _Scenario(
        id="vary",
        kind="negative",
        expected=_Expectation(status=CallStatus.BLOCKED),
        steps=[
            {
                "action": "repeat",
                "times": 3,
                "vary": "query",
                "step": {
                    "action": "tool_call",
                    "server": "jira",
                    "tool": "search",
                    "arguments": {"query": "ping"},
                },
            }
        ],
    )

    await ScenarioExecutor(client).run(scenario)

    assert [call[4] for call in client.tool_calls] == [
        {"query": "ping-0"},
        {"query": "ping-1"},
        {"query": "ping-2"},
    ]


async def test_chat_step_passes_max_tokens_to_the_client() -> None:
    client = FakeScenarioClient()
    scenario = _Scenario(
        id="mt",
        kind="negative",
        expected=_Expectation(status=CallStatus.BLOCKED),
        steps=[
            {
                "action": "repeat",
                "times": 2,
                "step": {"action": "chat", "message": "x", "max_tokens": 16},
            },
            {"action": "chat", "message": "y"},
        ],
    )

    await ScenarioExecutor(client).run(scenario)

    assert client.chat_max_tokens == [16, 16, None]


async def test_each_executor_run_uses_fresh_agent_sessions() -> None:
    first = FakeScenarioClient()
    second = FakeScenarioClient()
    scenario = _Scenario(
        id="s", kind="positive", expected=_Expectation(status=CallStatus.ALLOWED),
        steps=[_FIND_APPROVER_STEP],
    )

    await ScenarioExecutor(first, run_token="run1").run(scenario)
    await ScenarioExecutor(second, run_token="run2").run(scenario)

    assert first.tool_calls[0][1] == "selftest-s-run1"
    assert second.tool_calls[0][1] == "selftest-s-run2"


async def test_scripted_trace_lists_every_observation_with_call_ids() -> None:
    client = FakeScenarioClient()
    client.tool_call_results = [
        _obs(CallStatus.ALLOWED, call_id="c_1"),
        _obs(CallStatus.BLOCKED, rule_id="rate_limit", stage=StageName.behavior, call_id="c_2"),
    ]
    scenario = _Scenario(
        id="burst",
        kind="negative",
        expected=_Expectation(status=CallStatus.BLOCKED, rule_id="rate_limit"),
        steps=[
            {
                "action": "repeat",
                "times": 2,
                "step": {"action": "tool_call", "server": "jira", "tool": "search"},
            }
        ],
    )

    result = await ScenarioExecutor(client).run(scenario)

    assert [o.call_id for o in result.trace] == ["c_1", "c_2"]
    assert result.explanation.startswith("Expected BLOCKED")
    assert "behavior · rate_limit" in result.explanation


async def test_agent_trace_includes_every_turn_and_not_attempted_explanation() -> None:
    client = FakeScenarioClient()
    client.agent_chat_result = [
        _obs(CallStatus.ALLOWED, target="ci.get_run", call_id="c_1"),
        _obs(CallStatus.ALLOWED, target="llm.complete", call_id="c_2"),
    ]

    result = await ScenarioExecutor(client).run(_negative_hr(), tier="ollama")

    assert result.status == ScenarioStatus.NOT_ATTEMPTED
    assert [o.call_id for o in result.trace] == ["c_1", "c_2"]
    assert "it called ci.get_run instead" in result.explanation


async def test_exception_result_keeps_error_text_as_explanation() -> None:
    client = FakeScenarioClient()
    client.raise_on = "tool_call"
    scenario = _Scenario(
        id="boom",
        kind="negative",
        expected=_Expectation(status=CallStatus.BLOCKED),
        steps=[_FIND_APPROVER_STEP],
    )

    result = await ScenarioExecutor(client).run(scenario)

    assert result.status == ScenarioStatus.ERROR
    assert result.error == "boom"
    assert result.explanation == "boom"


def _flagged_scenario() -> _Scenario:
    return _Scenario(
        id="flag",
        kind="negative",
        expected=_Expectation(status=CallStatus.FLAGGED),
        steps=[_FIND_APPROVER_STEP],
    )


async def test_flagged_expectation_is_strict_in_scripted_tier() -> None:
    client = FakeScenarioClient()
    client.tool_call_results = [_obs(CallStatus.FLAGGED)]

    stopped = await ScenarioExecutor(client).run(_flagged_scenario())
    client.tool_call_results = [_obs(CallStatus.BLOCKED)]
    mismatch = await ScenarioExecutor(client).run(_flagged_scenario())

    assert stopped.status == ScenarioStatus.STOPPED
    assert mismatch.status == ScenarioStatus.ERROR


@pytest.mark.parametrize(
    "status", [CallStatus.FLAGGED, CallStatus.MASKED, CallStatus.BLOCKED, CallStatus.ESCALATED]
)
async def test_flagged_expectation_ollama_tier_stopped_by_detection_or_stronger(
    status: CallStatus,
) -> None:
    client = FakeScenarioClient()
    client.agent_chat_result = [_obs(status, target="hr-db.find_approver")]

    result = await ScenarioExecutor(client).run(_flagged_scenario(), tier="ollama")

    assert result.status == ScenarioStatus.STOPPED


async def test_flagged_expectation_ollama_tier_allowed_is_succeeded() -> None:
    client = FakeScenarioClient()
    client.agent_chat_result = [_obs(CallStatus.ALLOWED, target="hr-db.find_approver")]

    result = await ScenarioExecutor(client).run(_flagged_scenario(), tier="ollama")

    assert result.status == ScenarioStatus.SUCCEEDED
