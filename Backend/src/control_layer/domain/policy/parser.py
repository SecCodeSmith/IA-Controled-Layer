from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from control_layer.domain.exceptions import PolicyValidationError
from control_layer.domain.models.enums import InterceptionPoint, RuleAction, Severity, StageName
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule
from control_layer.domain.policy.vault import parse_vault_config

_DLP_TYPES = {"detectors", "sequence", "canary_token"}
_AUTHORIZATION_TYPES = {
    "rbac",
    "residency",
    "model_allowlist",
    "resource_scope",
    "resource_projection",
}
_POLICY_TYPES = {
    "signatures",
    "ml_classifier",
    "decision_tree",
    "llm_judge",
    "restricted_topics",
    "unsafe_output",
    "transaction_limit",
}
_BEHAVIOR_TYPES = {"rate_limit", "loop_guard", "circuit_breaker", "anomaly"}

_KNOWN_RULE_KEYS = {
    "id",
    "type",
    "stage",
    "on",
    "match",
    "detect",
    "action",
    "owasp",
    "severity",
    "enabled",
}


def infer_rule_type(rule_dict: dict[str, Any]) -> str:
    explicit_type = rule_dict.get("type")
    if explicit_type:
        return str(explicit_type)
    match = rule_dict.get("match")
    if match:
        if "action" in match:
            return "tool_match"
        if "sequence" in match:
            return "sequence"
    if rule_dict.get("detect"):
        return "detectors"
    return str(rule_dict["id"])


def infer_stage(rule_type: str, rule_dict: dict[str, Any]) -> StageName:
    if rule_type in _DLP_TYPES:
        return StageName.dlp
    if rule_type in _AUTHORIZATION_TYPES:
        return StageName.authorization
    if rule_type == "tool_match":
        if rule_dict.get("action") == RuleAction.require_approval:
            return StageName.authorization
        return StageName.policy
    if rule_type in _POLICY_TYPES:
        return StageName.policy
    if rule_type in _BEHAVIOR_TYPES:
        return StageName.behavior
    raise PolicyValidationError(f"cannot infer pipeline stage for rule type '{rule_type}'")


def _parse_on(rule_dict: dict[str, Any]) -> list[InterceptionPoint]:
    on_raw = rule_dict.get("on")
    if on_raw is None:
        return InterceptionPoint.all()
    if isinstance(on_raw, str):
        return [InterceptionPoint(on_raw)]
    return [InterceptionPoint(point) for point in on_raw]


def _parse_action(rule_dict: dict[str, Any]) -> RuleAction:
    action_raw = rule_dict.get("action")
    if action_raw is None:
        return RuleAction.flag
    try:
        return RuleAction(action_raw)
    except ValueError:
        raise PolicyValidationError(f"unknown rule action: {action_raw!r}") from None


def _parse_stage(rule_type: str, rule_dict: dict[str, Any]) -> StageName:
    explicit_stage = rule_dict.get("stage")
    if explicit_stage is None:
        return infer_stage(rule_type, rule_dict)
    try:
        return StageName(explicit_stage)
    except ValueError:
        raise PolicyValidationError(f"unknown pipeline stage: {explicit_stage!r}") from None


def _normalize_on_key(rule_dict: dict[str, Any]) -> dict[str, Any]:
    if True not in rule_dict:
        return rule_dict
    normalized = {key: value for key, value in rule_dict.items() if key is not True}
    normalized.setdefault("on", rule_dict[True])
    return normalized


def _parse_rule(rule_dict: dict[str, Any], seen_ids: set[str]) -> Rule:
    rule_dict = _normalize_on_key(rule_dict)
    rule_id = rule_dict.get("id")
    if not rule_id:
        raise PolicyValidationError("rule is missing an id")
    if rule_id in seen_ids:
        raise PolicyValidationError(f"duplicate rule id: {rule_id}")
    seen_ids.add(rule_id)

    rule_type = infer_rule_type(rule_dict)
    action = _parse_action(rule_dict)
    stage = _parse_stage(rule_type, rule_dict)
    on = _parse_on(rule_dict)
    params = {k: v for k, v in rule_dict.items() if k not in _KNOWN_RULE_KEYS}
    if params.get("vault"):
        parse_vault_config(params["vault"], rule_id)

    try:
        return Rule(
            id=rule_id,
            type=rule_type,
            stage=stage,
            on=on,
            match=rule_dict.get("match"),
            detect=rule_dict.get("detect"),
            action=action,
            params=params,
            owasp=rule_dict.get("owasp", []),
            severity=Severity(rule_dict.get("severity", Severity.medium)),
            enabled=rule_dict.get("enabled", True),
        )
    except (ValidationError, ValueError) as exc:
        raise PolicyValidationError(f"invalid rule '{rule_id}': {exc}") from exc


def parse_policy_document(data: dict[str, Any], source_hash: str) -> PolicyDocument:
    if "version" not in data:
        raise PolicyValidationError("policy document is missing 'version'")
    if "budgets" not in data:
        raise PolicyValidationError("policy document is missing 'budgets'")

    seen_ids: set[str] = set()
    rules = [_parse_rule(rule_dict, seen_ids) for rule_dict in data.get("rules", [])]

    try:
        return PolicyDocument(
            version=data["version"],
            profile=data.get("profile", "balanced"),
            models=data.get("models", {"allowed": [], "pricing": {}}),
            roles=data.get("roles", {}),
            locations=data.get("locations", {}),
            rules=rules,
            resources=data.get("resources") or [],
            budgets=data["budgets"],
            loaded_at=datetime.now(UTC),
            source_hash=source_hash,
        )
    except ValidationError as exc:
        raise PolicyValidationError(str(exc)) from exc
