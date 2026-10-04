from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from control_layer.domain.exceptions import PolicyValidationError
from control_layer.domain.models.enums import InterceptionPoint, RuleAction, StageName
from control_layer.domain.models.resource import ResourceConfig
from control_layer.domain.policy.parser import (
    infer_rule_type,
    infer_stage,
    parse_policy_document,
)

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


def test_parses_sample_policy_file_into_20_rules_with_expected_stages() -> None:
    data = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    document = parse_policy_document(data, source_hash="abc123")

    assert len(document.rules) == 20
    stages_by_id = {rule.id: rule.stage for rule in document.rules}
    assert stages_by_id == {
        "direct_push_to_main": StageName.policy,
        "destructive_requires_approval": StageName.authorization,
        "pii_masking": StageName.dlp,
        "external_send_after_untrusted_read": StageName.dlp,
        "prompt_injection_signatures": StageName.policy,
        "prompt_injection_tree": StageName.policy,
        "prompt_injection_ml": StageName.policy,
        "llm_judge": StageName.policy,
        "historical_exploits": StageName.policy,
        "secrets_detection": StageName.dlp,
        "data_residency": StageName.authorization,
        "role_provisioning": StageName.authorization,
        "resource_scope": StageName.authorization,
        "resource_projection": StageName.authorization,
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
    # PyYAML (YAML 1.1) reads an unquoted `on:` key as boolean True, so the sample file quotes it.
    data = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    document = parse_policy_document(data, source_hash="abc123")
    on_by_id = {rule.id: rule.on for rule in document.rules}

    assert on_by_id["pii_masking"] == [
        InterceptionPoint.response,
        InterceptionPoint.tool_result,
    ]
    assert on_by_id["external_send_after_untrusted_read"] == [
        InterceptionPoint.tool_call
    ]
    assert on_by_id["rate_limit"] == [
        InterceptionPoint.prompt,
        InterceptionPoint.tool_call,
    ]
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
        ("resource_scope", {}, StageName.authorization),
        ("resource_projection", {}, StageName.authorization),
        ("tool_match", {"action": "require_approval"}, StageName.authorization),
        ("tool_match", {"action": "block"}, StageName.policy),
        ("signatures", {}, StageName.policy),
        ("ml_classifier", {}, StageName.policy),
        ("decision_tree", {}, StageName.policy),
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
def test_infer_stage(
    rule_type: str, rule_dict: dict, expected_stage: StageName
) -> None:
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
        rules=[
            {
                "id": "r1",
                "on": ["prompt", "tool_result"],
                "detect": ["email"],
                "action": "mask",
            }
        ]
    )
    document = parse_policy_document(data, source_hash="h")
    assert document.rules[0].on == [
        InterceptionPoint.prompt,
        InterceptionPoint.tool_result,
    ]


def test_on_defaults_to_all_points_when_omitted() -> None:
    data = _minimal_document(
        rules=[{"id": "r1", "detect": ["email"], "action": "mask"}]
    )
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
    assert rule.params == {
        "block_at": 0.85,
        "escalate_at": 0.5,
        "escalate_to": "llm_judge",
    }


def test_missing_version_raises() -> None:
    data = _minimal_document()
    del data["version"]
    with pytest.raises(PolicyValidationError):
        parse_policy_document(data, source_hash="h")


def test_unknown_action_raises() -> None:
    data = _minimal_document(
        rules=[{"id": "r1", "detect": ["email"], "action": "nonsense"}]
    )
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


@pytest.mark.parametrize("rule_type", ["ml_classifier", "decision_tree", "llm_judge"])
def test_learned_rule_types_default_to_block_when_action_omitted(rule_type: str) -> None:
    data = _minimal_document(rules=[{"id": "r1", "type": rule_type}])
    document = parse_policy_document(data, source_hash="h")
    assert document.rules[0].action == RuleAction.block


@pytest.mark.parametrize("rule_type", ["ml_classifier", "decision_tree", "llm_judge"])
def test_explicit_action_overrides_learned_rule_default(rule_type: str) -> None:
    data = _minimal_document(rules=[{"id": "r1", "type": rule_type, "action": "flag"}])
    document = parse_policy_document(data, source_hash="h")
    assert document.rules[0].action == RuleAction.flag


@pytest.mark.parametrize("rule_type", ["signatures", "restricted_topics", "unsafe_output"])
def test_other_rule_types_still_default_to_flag_when_action_omitted(rule_type: str) -> None:
    data = _minimal_document(rules=[{"id": "r1", "type": rule_type}])
    document = parse_policy_document(data, source_hash="h")
    assert document.rules[0].action == RuleAction.flag


def test_sample_policy_learned_rules_block_explicitly() -> None:
    data = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    for rule in parse_policy_document(data, source_hash="h").rules:
        if rule.id in {"prompt_injection_tree", "prompt_injection_ml", "llm_judge"}:
            assert rule.action == RuleAction.block


@pytest.mark.parametrize("key", ["on", "'on'"])
def test_bare_and_quoted_on_key_in_yaml_text_are_honoured(key: str) -> None:
    text = (
        "version: 1\nbudgets: {per_user_tokens: 1, per_user_cost_usd: 1.0, "
        "max_tokens_per_request: 1, upstream_timeout_s: 1, warn_at_percent: 80}\n"
        f"rules:\n  - {{ id: r1, {key}: response, detect: [email], action: mask }}\n"
    )
    document = parse_policy_document(yaml.safe_load(text), source_hash="h")
    assert document.rules[0].on == [InterceptionPoint.response]


def test_sample_policy_tree_rule_precedes_logreg_rule_and_resource_rules_follow_rbac() -> (
    None
):
    data = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    ids = [rule.id for rule in parse_policy_document(data, source_hash="h").rules]

    assert ids.index("prompt_injection_tree") + 1 == ids.index("prompt_injection_ml")
    assert ids.index("role_provisioning") + 1 == ids.index("resource_scope")
    assert ids.index("resource_scope") + 1 == ids.index("resource_projection")


def test_sample_policy_tree_rule_params_and_resource_rule_actions() -> None:
    data = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    rules = {
        rule.id: rule for rule in parse_policy_document(data, source_hash="h").rules
    }

    tree = rules["prompt_injection_tree"]
    assert tree.type == "decision_tree"
    assert tree.action == RuleAction.block
    assert tree.params == {
        "block_at": 0.85,
        "escalate_at": 0.5,
        "verify_sample_rate": 0.2,
        "escalate_to": "llm_judge",
    }
    assert rules["resource_scope"].action == RuleAction.block
    assert rules["resource_scope"].on == [InterceptionPoint.tool_call]
    assert rules["resource_projection"].action == RuleAction.mask
    assert rules["resource_projection"].on == [InterceptionPoint.tool_result]


def test_sample_policy_resources_are_parsed() -> None:
    data = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    resources = {
        r.id: r for r in parse_policy_document(data, source_hash="h").resources
    }

    assert set(resources) == {
        "github_repo_files",
        "hr_directory_rows",
        "hr_employee_record",
    }
    files = resources["github_repo_files"]
    assert (files.server, files.tools, files.path_argument) == (
        "github",
        ["read_file"],
        "path",
    )
    assert files.roles["developer"].paths.deny == ["**/.env", "secrets/**", "**/*.pem"]
    rows = resources["hr_directory_rows"]
    assert (rows.server, rows.tools, rows.records) == ("hr-db", ["query"], "rows")
    assert rows.roles["hr"].columns.deny == ["salary"]
    assert rows.roles["hr"].rows == {"region": "$identity.region"}
    assert resources["hr_employee_record"].records is None


def test_resources_default_to_empty_list() -> None:
    document = parse_policy_document(_minimal_document(), source_hash="h")

    assert document.resources == []


def test_empty_resources_section_is_treated_as_empty_list() -> None:
    document = parse_policy_document(_minimal_document(resources=None), source_hash="h")

    assert document.resources == []


def test_resources_parsed_into_resource_config() -> None:
    data = _minimal_document(
        resources=[
            {
                "id": "files",
                "server": "github",
                "tools": ["read_file"],
                "path_argument": "path",
                "roles": {"*": {"paths": {"allow": ["README.md"]}}},
            }
        ]
    )

    document = parse_policy_document(data, source_hash="h")

    assert isinstance(document.resources[0], ResourceConfig)
    assert document.resources[0].roles["*"].paths.allow == ["README.md"]


@pytest.mark.parametrize(
    "resource",
    [
        {"server": "github"},
        {"id": "r", "server": "github", "roles": {"ceo": {}}},
        {"id": "r", "server": "github", "roles": {"hr": {"paths": "src/**"}}},
        {"id": "r", "server": "github", "unknown_key": True},
    ],
    ids=["missing-id", "unknown-role", "malformed-grant", "unknown-key"],
)
def test_invalid_resources_raise_policy_validation_error(resource: dict) -> None:
    with pytest.raises(PolicyValidationError):
        parse_policy_document(_minimal_document(resources=[resource]), source_hash="h")


def test_duplicate_resource_ids_raise_policy_validation_error() -> None:
    data = _minimal_document(
        resources=[{"id": "dup", "server": "github"}, {"id": "dup", "server": "hr-db"}]
    )

    with pytest.raises(PolicyValidationError, match="dup"):
        parse_policy_document(data, source_hash="h")


def _vault_rule(vault: object) -> dict:
    return {"id": "pii_masking", "detect": ["email"], "action": "mask", "vault": vault}


def test_vault_block_is_accepted_and_kept_in_params() -> None:
    vault = {"ttl_s": 60, "restore": {"email": ["mail.send"], "phone": ["mail.*"]}}
    document = parse_policy_document(_minimal_document(rules=[_vault_rule(vault)]), "h")
    assert document.rules[0].params["vault"] == vault


@pytest.mark.parametrize(
    "vault",
    [
        {"restore": {"api_key": ["mail.send"]}},
        {"restore": {"nonsense": ["mail.send"]}},
        {"restore": {"email": "mail send"}},
        {"restore": {"email": [1]}},
        {"ttl_s": 0},
        {"restore": ["email"]},
        "yes",
    ],
)
def test_invalid_vault_block_is_rejected(vault: object) -> None:
    with pytest.raises(PolicyValidationError):
        parse_policy_document(_minimal_document(rules=[_vault_rule(vault)]), "h")
