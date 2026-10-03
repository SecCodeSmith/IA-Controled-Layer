from __future__ import annotations

import yaml

from control_layer.application.audit.rule_yaml import rule_to_yaml
from control_layer.domain.policy.parser import parse_policy_document


def _policy():
    data = {
        "version": 1,
        "profile": "balanced",
        "models": {"allowed": ["mock"], "pricing": {}},
        "roles": {},
        "locations": {},
        "rules": [
            {
                "id": "pii_masking",
                "on": "response",
                "detect": ["email", "phone"],
                "action": "mask",
                "owasp": ["LLM02"],
            }
        ],
        "budgets": {
            "per_user_tokens": 1000,
            "per_user_cost_usd": 1.0,
            "max_tokens_per_request": 100,
            "upstream_timeout_s": 30,
            "warn_at_percent": 80,
            "on_exceeded": "block",
        },
    }
    return parse_policy_document(data, source_hash="h")


def test_rule_to_yaml_round_trips_to_a_readable_mapping() -> None:
    rule = _policy().rules[0]
    text = rule_to_yaml(rule)
    parsed = yaml.safe_load(text)
    assert isinstance(parsed, list)
    entry = parsed[0]
    assert entry["id"] == "pii_masking"
    assert entry["on"] == "response"
    assert entry["detect"] == ["email", "phone"]
    assert entry["action"] == "mask"
    assert entry["owasp"] == ["LLM02"]


def test_rule_to_yaml_is_a_string() -> None:
    rule = _policy().rules[0]
    assert isinstance(rule_to_yaml(rule), str)
