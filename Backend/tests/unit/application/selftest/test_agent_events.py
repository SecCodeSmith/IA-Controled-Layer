from __future__ import annotations

from control_layer.application.selftest.agent_events import observations_from_events
from control_layer.domain.models.enums import CallStatus, StageName


def test_tool_call_event_target_is_the_qualified_tool() -> None:
    events = [
        {
            "type": "tool_call",
            "tool": "ci.get_run",
            "status": "ALLOWED",
            "stage": "authorization",
            "rule_id": None,
        }
    ]

    [observation] = observations_from_events(events)

    assert observation.target == "ci.get_run"
    assert observation.status == CallStatus.ALLOWED
    assert observation.stage == StageName.authorization


def test_approval_required_event_carries_tool_and_approval_id() -> None:
    events = [
        {
            "type": "approval_required",
            "approval_id": "ap_1",
            "tool": "github.delete_branch",
            "rule_id": "destructive_requires_approval",
        }
    ]

    [observation] = observations_from_events(events)

    assert observation.target == "github.delete_branch"
    assert observation.status == CallStatus.ESCALATED
    assert observation.approval_id == "ap_1"


def test_assistant_text_and_notice_map_to_llm_complete() -> None:
    events = [
        {"type": "assistant_text", "text": "hi", "status": "ALLOWED"},
        {"type": "notice", "status": "BLOCKED", "rule_id": "model_allowlist"},
        {"type": "assistant_text", "text": "no status"},
    ]

    observations = observations_from_events(events)

    assert [o.target for o in observations] == ["llm.complete", "llm.complete"]
