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
