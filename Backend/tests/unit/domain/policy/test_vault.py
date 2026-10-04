from __future__ import annotations

from control_layer.domain.policy.parser import parse_policy_document
from control_layer.domain.policy.vault import restorable_kinds_for_tool
from tests.unit.domain.policy.test_parser import _minimal_document


def _policy(restore: dict):  # noqa: ANN202
    rule = {
        "id": "pii_masking",
        "detect": ["email", "phone"],
        "action": "mask",
        "vault": {"restore": restore},
    }
    return parse_policy_document(_minimal_document(rules=[rule]), "h")


def test_restorable_kinds_match_tool_patterns() -> None:
    policy = _policy({"email": ["mail.send"], "phone": ["mail.*"]})
    assert restorable_kinds_for_tool(policy, "mail.send") == {"email", "phone"}
    assert restorable_kinds_for_tool(policy, "mail.draft") == {"phone"}
    assert restorable_kinds_for_tool(policy, "github.push") == frozenset()


def test_no_vault_means_nothing_is_restorable() -> None:
    rule = {"id": "pii_masking", "detect": ["email"], "action": "mask"}
    policy = parse_policy_document(_minimal_document(rules=[rule]), "h")
    assert restorable_kinds_for_tool(policy, "mail.send") == frozenset()
