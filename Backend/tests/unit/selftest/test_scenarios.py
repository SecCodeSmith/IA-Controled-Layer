from __future__ import annotations

from pathlib import Path

import yaml

from control_layer.domain.policy.parser import parse_policy_document
from control_layer.selftest.scenarios import SCENARIOS

_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "policy.yaml"

_CONTRACT_USER_SUBS = {
    "anna.kowalska",
    "marek.nowak",
    "john.smith",
    "ewa.zielinska",
}


def _policy_rule_ids() -> set[str]:
    data = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    document = parse_policy_document(data, source_hash="integrity-check")
    return {rule.id for rule in document.rules}


def test_scenario_ids_are_unique() -> None:
    ids = [scenario.id for scenario in SCENARIOS]
    assert len(ids) == len(set(ids))


def test_scenario_rule_ids_exist_in_policy_yaml() -> None:
    rule_ids = _policy_rule_ids()
    for scenario in SCENARIOS:
        if scenario.expected.rule_id is not None:
            assert scenario.expected.rule_id in rule_ids, (
                f"{scenario.id} references unknown rule_id {scenario.expected.rule_id!r}"
            )


def test_scenario_actors_exist_in_contract_users_table() -> None:
    for scenario in SCENARIOS:
        assert scenario.actor in _CONTRACT_USER_SUBS, (
            f"{scenario.id} references unknown actor {scenario.actor!r}"
        )


def test_catalogue_has_both_positive_and_negative_scenarios() -> None:
    kinds = {scenario.kind for scenario in SCENARIOS}
    assert kinds == {"positive", "negative"}


def test_every_scenario_has_a_prompt_and_at_least_one_step() -> None:
    for scenario in SCENARIOS:
        assert scenario.prompt
        assert len(scenario.steps) >= 1


def test_deterministic_scenarios_are_not_agent_driven() -> None:
    from control_layer.selftest.scenarios import SCENARIOS

    scripted_only = {s.id for s in SCENARIOS if not s.agent_driven}

    assert scripted_only == {
        "spoofed_role_tampered_token",
        "expired_token",
        "forbidden_model",
        "rate_limit_burst",
        "loop_guard_repeat",
        "block_burst_quarantine",
        "token_budget_overrun",
        "tampered_sub_impersonation",
        "tampered_region_claim",
        "expired_token_chat",
        "max_tokens_over_budget",
        "loop_guard_repeat_hr_lookup",
        "unknown_tool_blocked",
    }


def _registered_tools() -> set[str]:
    path = _CONFIG_PATH.with_name("mcp_servers.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        f"{server['name']}.{tool}" for server in data["servers"] for tool in server.get("tools", {})
    }


def _walk_steps(steps: list[dict]) -> list[dict]:
    flat: list[dict] = []
    for step in steps:
        flat.append(step)
        if step["action"] == "repeat":
            flat.extend(_walk_steps([step["step"]]))
    return flat


def test_catalogue_has_at_least_forty_scenarios_with_both_kinds() -> None:
    assert len(SCENARIOS) >= 40
    assert sum(1 for s in SCENARIOS if s.kind == "positive") >= 12
    assert sum(1 for s in SCENARIOS if s.kind == "negative") >= 25


def test_every_scenario_has_a_description_and_prompt() -> None:
    for scenario in SCENARIOS:
        assert scenario.description.strip(), f"{scenario.id} has no description"
        assert scenario.prompt.strip(), f"{scenario.id} has no prompt"


def test_every_scenario_has_a_name_and_unique_id_slug() -> None:
    names = [s.name for s in SCENARIOS]
    assert len(names) == len(set(names))
    for scenario in SCENARIOS:
        assert scenario.id == scenario.id.lower().replace(" ", "_")


def test_tool_call_steps_name_registered_tools() -> None:
    known = _registered_tools()
    unregistered_by_design = {"unknown_tool_blocked"}
    for scenario in SCENARIOS:
        if scenario.id in unregistered_by_design:
            continue
        for step in _walk_steps(scenario.steps):
            if step["action"] == "tool_call":
                name = f"{step['server']}.{step['tool']}"
                assert name in known, f"{scenario.id} calls unknown tool {name}"


def test_step_actions_are_supported() -> None:
    supported = {
        "tool_call",
        "chat",
        "approve",
        "tamper_token",
        "use_expired_token",
        "repeat",
    }
    for scenario in SCENARIOS:
        for step in _walk_steps(scenario.steps):
            assert step["action"] in supported, f"{scenario.id}: {step['action']}"


def test_catalogue_covers_every_pipeline_stage_and_owasp_families() -> None:
    stages = {s.stage.value for s in SCENARIOS}
    assert {"identity", "authorization", "policy", "dlp", "behavior", "resource"} <= stages
    tags = {tag for s in SCENARIOS for tag in s.owasp}
    assert {"LLM01", "LLM02", "LLM03", "LLM06", "LLM07", "LLM10"} <= tags
    assert {"ASI01", "ASI02", "ASI03", "ASI05", "ASI08", "ASI10"} <= tags


def test_pan_in_tool_result_is_deterministic_masking_scenario() -> None:
    scenario = next(s for s in SCENARIOS if s.id == "pan_in_tool_result")
    assert scenario.actor == "ewa.zielinska"
    assert scenario.owasp == ["LLM02"]
    assert scenario.agent_driven is True
    assert scenario.expected.rule_id == "pii_masking"
    assert scenario.steps == [
        {
            "action": "tool_call",
            "server": "payments",
            "tool": "get_card",
            "arguments": {"account": "ACC-1001"},
        }
    ]
    assert all(s.id != "pan_in_model_response" for s in SCENARIOS)
