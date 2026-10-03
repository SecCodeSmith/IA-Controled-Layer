from control_layer.domain.exceptions import (
    AgentUnavailableError,
    ApprovalNotFoundError,
    CallNotFoundError,
    ControlLayerError,
    PolicyViolationError,
    UnknownToolError,
)
from control_layer.domain.models.decision import Violation
from control_layer.domain.models.enums import CallStatus, RuleAction, Severity, StageName


def test_control_layer_error_defaults_call_id_to_none() -> None:
    error = ControlLayerError("boom")
    assert error.call_id is None


def test_control_layer_error_call_id_is_settable_per_instance() -> None:
    first = ControlLayerError("boom")
    second = ControlLayerError("bang")
    first.call_id = "c_000001"
    assert first.call_id == "c_000001"
    assert second.call_id is None


def test_policy_violation_error_exposes_violation_and_status() -> None:
    violation = Violation(
        stage=StageName.authorization,
        rule_id="role_provisioning",
        action=RuleAction.block,
        severity=Severity.high,
        owasp=["ASI03"],
        evidence=[],
        confidence=1.0,
        reason="HR database is not provisioned for the Developer role",
    )
    error = PolicyViolationError(violation, CallStatus.BLOCKED)
    assert error.violation is violation
    assert error.status == CallStatus.BLOCKED
    assert isinstance(error, ControlLayerError)


def test_approval_not_found_error_carries_approval_id() -> None:
    error = ApprovalNotFoundError("ap_missing")
    assert error.approval_id == "ap_missing"
    assert isinstance(error, ControlLayerError)


def test_unknown_tool_error_carries_server_and_tool() -> None:
    error = UnknownToolError("github", "delete_everything")
    assert error.server == "github"
    assert error.tool == "delete_everything"


def test_call_not_found_error_carries_call_id() -> None:
    error = CallNotFoundError("c_999999")
    assert error.call_id == "c_999999"


def test_agent_unavailable_error_carries_reason() -> None:
    error = AgentUnavailableError("Ollama is not reachable")
    assert error.reason == "Ollama is not reachable"
