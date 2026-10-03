from __future__ import annotations

from enum import StrEnum


class CallStatus(StrEnum):
    ALLOWED = "ALLOWED"
    MASKED = "MASKED"
    BLOCKED = "BLOCKED"
    ESCALATED = "ESCALATED"
    FLAGGED = "FLAGGED"


class StageName(StrEnum):
    identity = "identity"
    authorization = "authorization"
    dlp = "dlp"
    policy = "policy"
    behavior = "behavior"
    resource = "resource"
    audit = "audit"

    @classmethod
    def ordered(cls) -> list[StageName]:
        return [
            cls.identity,
            cls.authorization,
            cls.dlp,
            cls.policy,
            cls.behavior,
            cls.resource,
            cls.audit,
        ]


class InterceptionPoint(StrEnum):
    prompt = "prompt"
    response = "response"
    tool_call = "tool_call"
    tool_result = "tool_result"

    @classmethod
    def all(cls) -> list[InterceptionPoint]:
        return [cls.prompt, cls.response, cls.tool_call, cls.tool_result]


class RuleAction(StrEnum):
    allow = "allow"
    flag = "flag"
    mask = "mask"
    block = "block"
    require_approval = "require_approval"
    quarantine = "quarantine"


class Role(StrEnum):
    developer = "developer"
    hr = "hr"
    finance = "finance"


class ApprovalStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    executed = "executed"
    expired = "expired"


class Severity(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class CallKind(StrEnum):
    chat = "chat"
    tool_call = "tool_call"
