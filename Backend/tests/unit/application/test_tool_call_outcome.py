from __future__ import annotations

from control_layer.application.use_cases.outcomes import ToolCallOutcome
from control_layer.domain.models.decision import Decision
from control_layer.domain.models.enums import CallStatus, RuleAction


def test_tool_call_outcome_decision_defaults_to_none() -> None:
    assert ToolCallOutcome(call_id="CL-1", status=CallStatus.ALLOWED).decision is None


def test_tool_call_outcome_carries_decision() -> None:
    decision = Decision(status=CallStatus.BLOCKED, action=RuleAction.block)

    outcome = ToolCallOutcome(call_id="CL-1", status=CallStatus.BLOCKED, decision=decision)

    assert outcome.decision == decision
