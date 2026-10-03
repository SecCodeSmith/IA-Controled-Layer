from __future__ import annotations

from datetime import UTC, datetime

from control_layer.application.use_cases.admin.policy_view import (
    GetPolicyViewUseCase,
    ReloadPolicyUseCase,
)
from control_layer.domain.models.enums import StageName
from control_layer.domain.policy.parser import parse_policy_document

_DOCUMENT_DATA = {
    "version": 3,
    "profile": "balanced",
    "models": {"allowed": ["mock"], "pricing": {}},
    "roles": {"developer": {"mcp_servers": ["github"]}},
    "locations": {},
    "rules": [
        {
            "id": "pii_masking",
            "on": "response",
            "detect": ["email"],
            "action": "mask",
            "owasp": ["LLM02"],
            "severity": "medium",
        },
        {
            "id": "role_provisioning",
            "type": "rbac",
            "action": "block",
            "owasp": ["ASI03"],
        },
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


class FakePolicyRepository:
    def __init__(self) -> None:
        self.document = parse_policy_document(_DOCUMENT_DATA, source_hash="hash-1")
        self.reload_calls = 0

    async def current(self):
        return self.document

    async def reload(self):
        self.reload_calls += 1
        return self.document

    async def status(self) -> dict:
        return {
            "version": self.document.version,
            "status": "LOADED",
            "loaded_at": datetime.now(UTC),
            "source": "config/policy.yaml",
            "error": None,
            "raw_yaml": "version: 3\n",
        }


async def test_rules_by_stage_includes_every_stage_in_order_with_empty_lists() -> None:
    use_case = GetPolicyViewUseCase(FakePolicyRepository())

    view = await use_case.execute()

    assert list(view.rules_by_stage.keys()) == [s.value for s in StageName.ordered()]
    assert view.rules_by_stage["identity"] == []
    assert view.rules_by_stage["behavior"] == []
    assert view.rules_by_stage["audit"] == []


async def test_rules_are_grouped_under_their_inferred_stage() -> None:
    use_case = GetPolicyViewUseCase(FakePolicyRepository())

    view = await use_case.execute()

    dlp_rule_ids = [r["id"] for r in view.rules_by_stage["dlp"]]
    authorization_rule_ids = [r["id"] for r in view.rules_by_stage["authorization"]]
    assert dlp_rule_ids == ["pii_masking"]
    assert authorization_rule_ids == ["role_provisioning"]


async def test_rule_dict_has_the_documented_fields() -> None:
    use_case = GetPolicyViewUseCase(FakePolicyRepository())

    view = await use_case.execute()

    rule = view.rules_by_stage["dlp"][0]
    assert set(rule.keys()) == {
        "id",
        "type",
        "action",
        "on",
        "owasp",
        "severity",
        "enabled",
        "overridden",
        "params",
    }
    assert rule["id"] == "pii_masking"
    assert rule["action"] == "mask"
    assert rule["on"] == ["response"]
    assert rule["owasp"] == ["LLM02"]
    assert rule["enabled"] is True


async def test_status_and_raw_yaml_come_from_policy_repository_status() -> None:
    use_case = GetPolicyViewUseCase(FakePolicyRepository())

    view = await use_case.execute()

    assert view.version == 3
    assert view.status == "LOADED"
    assert view.source == "config/policy.yaml"
    assert view.raw_yaml == "version: 3\n"
    assert view.error is None


async def test_reload_use_case_reloads_then_returns_the_policy_view() -> None:
    repository = FakePolicyRepository()
    use_case = ReloadPolicyUseCase(repository)

    view = await use_case.execute()

    assert repository.reload_calls == 1
    assert view.version == 3
