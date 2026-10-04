from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from control_layer.application.selftest.agent_events import observations_from_events
from control_layer.application.use_cases.outcomes import ToolCallOutcome
from control_layer.domain.exceptions import RateLimitedError
from control_layer.domain.models.enums import CallStatus, StageName
from control_layer.presentation.selftest.in_process_client import (
    InProcessScenarioClient,
    observation_from_error,
    observation_from_outcome,
)


class _FakeUseCase:
    def __init__(self, result: Any) -> None:
        self._result = result

    async def execute(self, token: str, session_id: str, request: Any) -> Any:
        return self._result


def _client(chat: Any = None, tool: Any = None) -> InProcessScenarioClient:
    provider = SimpleNamespace(describe=lambda: SimpleNamespace(model="m"))
    return InProcessScenarioClient(chat, tool, None, None, None, provider)  # type: ignore[arg-type]


def test_tool_outcome_carries_call_id() -> None:
    outcome = ToolCallOutcome(call_id="c_7", status=CallStatus.ALLOWED)

    assert observation_from_outcome(outcome, "ci.get_run").call_id == "c_7"


def test_error_observation_carries_the_exception_call_id() -> None:
    exc = RateLimitedError("slow down")
    exc.call_id = "c_9"  # type: ignore[attr-defined]

    observation = observation_from_error(exc, "jira.search")

    assert observation.call_id == "c_9"
    assert observation.stage == StageName.behavior


async def test_chat_observation_carries_outcome_call_id() -> None:
    outcome = SimpleNamespace(
        call_id="c_3", status=CallStatus.ALLOWED, stage=None, rule_id=None, reason=None
    )

    observation = await _client(chat=_FakeUseCase(outcome)).chat("t", "s", "hi")

    assert observation.call_id == "c_3"
    assert observation.target == "llm.complete"


async def test_tool_call_observation_carries_outcome_call_id() -> None:
    outcome = ToolCallOutcome(call_id="c_4", status=CallStatus.ALLOWED)

    client = _client(tool=_FakeUseCase(outcome))
    observation = await client.tool_call("t", "s", "ci", "get_run", {})

    assert observation.call_id == "c_4"


def test_agent_events_propagate_call_id() -> None:
    events = [
        {"type": "tool_call", "tool": "ci.get_run", "status": "ALLOWED", "call_id": "c_1"},
        {"type": "assistant_text", "text": "x", "status": "ALLOWED", "call_id": "c_2"},
        {"type": "notice", "status": "BLOCKED", "call_id": "c_3"},
        {"type": "approval_required", "approval_id": "ap", "tool": "a.b", "call_id": "c_4"},
        {"type": "notice", "status": "BLOCKED"},
    ]

    observations = observations_from_events(events)

    assert [o.call_id for o in observations] == ["c_1", "c_2", "c_3", "c_4", None]
