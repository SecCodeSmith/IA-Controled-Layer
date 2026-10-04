from control_layer.domain.models.enums import (
    ApprovalStatus,
    CallKind,
    CallStatus,
    InterceptionPoint,
    Role,
    RuleAction,
    Severity,
    StageName,
)


def test_call_status_members() -> None:
    assert {member.value for member in CallStatus} == {
        "ALLOWED",
        "MASKED",
        "BLOCKED",
        "ESCALATED",
        "FLAGGED",
    }


def test_stage_name_ordered() -> None:
    assert StageName.ordered() == [
        StageName.identity,
        StageName.authorization,
        StageName.dlp,
        StageName.policy,
        StageName.behavior,
        StageName.resource,
        StageName.audit,
    ]


def test_stage_name_members_match_contract() -> None:
    assert {member.value for member in StageName} == {
        "identity",
        "authorization",
        "dlp",
        "policy",
        "behavior",
        "resource",
        "audit",
    }


def test_interception_point_members() -> None:
    assert {member.value for member in InterceptionPoint} == {
        "prompt",
        "response",
        "tool_call",
        "tool_result",
    }


def test_interception_point_all() -> None:
    assert InterceptionPoint.all() == [
        InterceptionPoint.prompt,
        InterceptionPoint.response,
        InterceptionPoint.tool_call,
        InterceptionPoint.tool_result,
    ]


def test_rule_action_members() -> None:
    assert {member.value for member in RuleAction} == {
        "allow",
        "flag",
        "mask",
        "block",
        "require_approval",
        "quarantine",
    }


def test_role_members() -> None:
    assert {member.value for member in Role} == {"developer", "hr", "finance", "admin"}


def test_approval_status_members() -> None:
    assert {member.value for member in ApprovalStatus} == {
        "pending",
        "approved",
        "rejected",
        "executed",
        "expired",
    }


def test_severity_members() -> None:
    assert {member.value for member in Severity} == {"low", "medium", "high", "critical"}


def test_call_kind_members() -> None:
    assert {member.value for member in CallKind} == {"chat", "tool_call", "workbench", "admin"}
