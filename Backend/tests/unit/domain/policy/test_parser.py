from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from control_layer.domain.exceptions import PolicyValidationError
from control_layer.domain.models.enums import InterceptionPoint, RuleAction, StageName
from control_layer.domain.policy.parser import infer_rule_type, infer_stage, parse_policy_document

_CONFIG_PATH = Path(__file__).resolve().parents[4] / "config" / "policy.yaml"


def _minimal_document(**overrides: object) -> dict:
    base: dict = {
        "version": 1,
        "profile": "balanced",
        "models": {"allowed": ["mock"], "pricing": {}},
        "roles": {"developer": {"mcp_servers": ["github"]}},
        "locations": {},
        "rules": [],
        "budgets": {
            "per_user_tokens": 1000,
            "per_user_cost_usd": 1.0,
            "max_tokens_per_request": 100,
            "upstream_timeout_s": 30,
            "warn_at_percent": 80,
            "on_exceeded": "block",
        },
    }
    base.update(overrides)
    return base


def test_parses_sample_policy_file_into_17_rules_with_expected_stages() -> None:
    data = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    document = parse_policy_document(data, source_hash="abc123")

    assert len(document.rules) == 17
    stages_by_id = {rule.id: rule.stage for rule in document.rules}
    assert stages_by_id == {
        "direct_push_to_main": StageName.policy,
        "destructive_requires_approval": StageName.authorization,
        "pii_masking": StageName.dlp,
        "external_send_after_untrusted_read": StageName.dlp,
        "prompt_injection_signatures": StageName.policy,
        "prompt_injection_ml": StageName.policy,
        "llm_judge": StageName.policy,
        "historical_exploits": StageName.policy,
        "secrets_detection": StageName.dlp,
        "data_residency": StageName.authorization,
        "role_provisioning": StageName.authorization,
        "rate_limit": StageName.behavior,
        "loop_guard": StageName.behavior,
        "circuit_breaker": StageName.authorization,
        "model_allowlist": StageName.authorization,
        "transaction_limit": StageName.policy,
        "anomaly_first_destructive_use": StageName.behavior,
    }
    assert document.version == 3
    assert document.source_hash == "abc123"


def test_sample_policy_rules_have_the_intended_on_points_not_all_four() -> None:
    # Regression guard: an unquoted `on:` key is parsed by PyYAML as the boolean key
    # `True` (YAML 1.1 on/off/yes/no resolution), which would silently make every rule
    # fall back to "on: all four points". The sample file quotes the key for this reason.
    data = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    document = parse_policy_document(data, source_hash="abc123")
    on_by_id = {rule.id: rule.on for rule in document.rules}

    assert on_by_id["pii_masking"] == [InterceptionPoint.response, InterceptionPoint.tool_result]
    assert on_by_id["external_send_after_untrusted_read"] == [InterceptionPoint.tool_call]
    assert on_by_id["rate_limit"] == [InterceptionPoint.prompt, InterceptionPoint.tool_call]
    assert on_by_id["llm_judge"] == []
    assert on_by_id["direct_push_to_main"] == [InterceptionPoint.tool_call]


def test_infer_rule_type_tool_match_from_match_action() -> None:
    assert infer_rule_type({"match": {"action": ["delete_*"]}}) == "tool_match"


def test_infer_rule_type_sequence_from_match_sequence() -> None:
    assert infer_rule_type({"match": {"sequence": ["a", "b"]}}) == "sequence"


def test_infer_rule_type_detectors_from_detect() -> None:
    assert infer_rule_type({"detect": ["email"]}) == "detectors"


def test_infer_rule_type_explicit_wins() -> None:
    assert infer_rule_type({"type": "rbac", "detect": ["email"]}) == "rbac"


def test_infer_rule_type_falls_back_to_id() -> None:
    assert infer_rule_type({"id": "rate_limit"}) == "rate_limit"


@pytest.mark.parametrize(
    ("rule_type", "rule_dict", "expected_stage"),
    [
        ("detectors", {}, StageName.dlp),
        ("sequence", {}, StageName.dlp),
        ("canary_token", {}, StageName.dlp),
        ("rbac", {}, StageName.authorization),
        ("residency", {}, StageName.authorization),
        ("model_allowlist", {}, StageName.authorization),
        ("tool_match", {"action": "require_approval"}, StageName.authorization),
        ("tool_match", {"action": "block"}, StageName.policy),
        ("signatures", {}, StageName.policy),
        ("ml_classifier", {}, StageName.policy),
        ("llm_judge", {}, StageName.policy),
        ("restricted_topics", {}, StageName.policy),
        ("unsafe_output", {}, StageName.policy),
        ("transaction_limit", {}, StageName.policy),
        ("rate_limit", {}, StageName.behavior),
        ("loop_guard", {}, StageName.behavior),
        ("circuit_breaker", {}, StageName.behavior),
        ("anomaly", {}, StageName.behavior),
    ],
)
def test_infer_stage(rule_type: str, rule_dict: dict, expected_stage: StageName) -> None:
    assert infer_stage(rule_type, rule_dict) == expected_stage


def test_explicit_stage_overrides_inference() -> None:
    data = _minimal_document(
        rules=[
            {
                "id": "custom_detector_in_policy_stage",
                "detect": ["email"],
                "stage": "policy",
                "action": "mask",
            }
        ]
    )
    document = parse_policy_document(data, source_hash="h")
    assert document.rules[0].stage == StageName.policy


def test_on_accepts_single_string() -> None:
    data = _minimal_document(
        rules=[{"id": "r1", "on": "prompt", "detect": ["email"], "action": "mask"}]
    )
    document = parse_policy_document(data, source_hash="h")
    assert document.rules[0].on == [InterceptionPoint.prompt]


def test_on_accepts_list() -> None:
    data = _minimal_document(
        rules=[{"id": "r1", "on": ["prompt", "tool_result"], "detect": ["email"], "action": "mask"}]
    )
    document = parse_policy_document(data, source_hash="h")
    assert document.rules[0].on == [InterceptionPoint.prompt, InterceptionPoint.tool_result]


def test_on_defaults_to_all_points_when_omitted() -> None:
    data = _minimal_document(rules=[{"id": "r1", "detect": ["email"], "action": "mask"}])
    document = parse_policy_document(data, source_hash="h")
    assert document.rules[0].on == InterceptionPoint.all()


def test_unknown_fields_go_to_params() -> None:
    data = _minimal_document(
        rules=[
            {
                "id": "prompt_injection_ml",
                "type": "ml_classifier",
                "block_at": 0.85,
                "escalate_at": 0.5,
                "escalate_to": "llm_judge",
            }
        ]
    )
    document = parse_policy_document(data, source_hash="h")
    rule = document.rules[0]
    assert rule.params == {"block_at": 0.85, "escalate_at": 0.5, "escalate_to": "llm_judge"}


def test_missing_version_raises() -> None:
    data = _minimal_document()
    del data["version"]
    with pytest.raises(PolicyValidationError):
        parse_policy_document(data, source_hash="h")


def test_unknown_action_raises() -> None:
    data = _minimal_document(rules=[{"id": "r1", "detect": ["email"], "action": "nonsense"}])
    with pytest.raises(PolicyValidationError):
        parse_policy_document(data, source_hash="h")


def test_unknown_stage_raises() -> None:
    data = _minimal_document(
        rules=[{"id": "r1", "detect": ["email"], "action": "mask", "stage": "nonsense"}]
    )
    with pytest.raises(PolicyValidationError):
        parse_policy_document(data, source_hash="h")


def test_duplicate_rule_ids_raise() -> None:
    data = _minimal_document(
        rules=[
            {"id": "dup", "detect": ["email"], "action": "mask"},
            {"id": "dup", "detect": ["phone"], "action": "mask"},
        ]
    )
    with pytest.raises(PolicyValidationError):
        parse_policy_document(data, source_hash="h")


def test_rule_action_default_is_flag_when_action_omitted() -> None:
    data = _minimal_document(rules=[{"id": "llm_judge", "type": "llm_judge"}])
    document = parse_policy_document(data, source_hash="h")
    assert document.rules[0].action == RuleAction.flag


@pytest.mark.parametrize("key", ["on", "'on'"])
def test_bare_and_quoted_on_key_in_yaml_text_are_honoured(key: str) -> None:
    text = (
        "version: 1\nbudgets: {per_user_tokens: 1, per_user_cost_usd: 1.0, "
        "max_tokens_per_request: 1, upstream_timeout_s: 1, warn_at_percent: 80}\n"
        f"rules:\n  - {{ id: r1, {key}: response, detect: [email], action: mask }}\n"
    )
    document = parse_policy_document(yaml.safe_load(text), source_hash="h")
    assert document.rules[0].on == [InterceptionPoint.response]
