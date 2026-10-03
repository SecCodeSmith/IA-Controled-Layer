from __future__ import annotations

from control_layer.domain.models.decision import Violation
from control_layer.domain.models.enums import CallStatus


class ControlLayerError(Exception):
    call_id: str | None = None


class IdentityRejectedError(ControlLayerError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class PolicyViolationError(ControlLayerError):
    def __init__(self, violation: Violation, status: CallStatus) -> None:
        super().__init__(violation.reason or violation.rule_id)
        self.violation = violation
        self.status = status


class QuarantinedError(ControlLayerError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class RateLimitedError(ControlLayerError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class BudgetExceededError(ControlLayerError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ApprovalRequiredError(ControlLayerError):
    def __init__(self, approval_id: str, rule_id: str, reason: str) -> None:
        super().__init__(reason)
        self.approval_id = approval_id
        self.rule_id = rule_id
        self.reason = reason


class UpstreamProviderError(ControlLayerError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class PolicyValidationError(ControlLayerError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class UnknownEvaluatorError(ControlLayerError):
    def __init__(self, rule_type: str) -> None:
        super().__init__(f"No evaluator registered for rule type '{rule_type}'")
        self.rule_type = rule_type


class ApprovalNotFoundError(ControlLayerError):
    def __init__(self, approval_id: str) -> None:
        super().__init__(f"approval not found: {approval_id}")
        self.approval_id = approval_id


class UnknownToolError(ControlLayerError):
    def __init__(self, server: str, tool: str) -> None:
        super().__init__(f"unknown tool: {server}.{tool}")
        self.server = server
        self.tool = tool


class CallNotFoundError(ControlLayerError):
    def __init__(self, call_id: str) -> None:
        super().__init__(f"call not found: {call_id}")
        self.call_id = call_id


class AgentUnavailableError(ControlLayerError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class RuleNotFoundError(ControlLayerError):
    def __init__(self, rule_id: str) -> None:
        super().__init__(f"rule not found: {rule_id}")
        self.rule_id = rule_id


class ModelNotAvailableError(ControlLayerError):
    def __init__(self, provider: str, model: str) -> None:
        super().__init__(f"model not available: {provider}/{model}")
        self.provider = provider
        self.model = model
