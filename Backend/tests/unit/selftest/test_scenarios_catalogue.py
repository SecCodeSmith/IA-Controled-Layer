from __future__ import annotations

from control_layer.domain.models.enums import CallStatus, StageName
from control_layer.selftest.scenarios import SCENARIOS


def test_scenarios_catalogue_has_69_entries() -> None:
    assert len(SCENARIOS) == 69


def test_scenarios_has_20_positive_and_49_negative() -> None:
    positive = [s for s in SCENARIOS if s.kind == "positive"]
    negative = [s for s in SCENARIOS if s.kind == "negative"]
    assert len(positive) == 20
    assert len(negative) == 49


def test_scenario_ids_are_unique() -> None:
    ids = [s.id for s in SCENARIOS]
    assert len(ids) == len(set(ids))


def test_required_scenario_ids_exist() -> None:
    required_ids = {
        "dev_reads_allowed_repo_file",
        "dev_reads_env_file_blocked",
        "hr_query_projected",
    }
    scenario_ids = {s.id for s in SCENARIOS}
    assert required_ids.issubset(scenario_ids)


def test_dev_reads_allowed_repo_file_expectations() -> None:
    scenario = next((s for s in SCENARIOS if s.id == "dev_reads_allowed_repo_file"), None)
    assert scenario is not None
    assert scenario.kind == "positive"
    assert scenario.actor == "anna.kowalska"
    assert scenario.stage == StageName.authorization
    assert scenario.expected.status == CallStatus.ALLOWED


def test_dev_reads_env_file_blocked_expectations() -> None:
    scenario = next((s for s in SCENARIOS if s.id == "dev_reads_env_file_blocked"), None)
    assert scenario is not None
    assert scenario.kind == "negative"
    assert scenario.actor == "anna.kowalska"
    assert scenario.stage == StageName.authorization
    assert scenario.expected.status == CallStatus.BLOCKED
    assert scenario.expected.rule_id == "resource_scope"


def test_hr_query_projected_expectations() -> None:
    scenario = next((s for s in SCENARIOS if s.id == "hr_query_projected"), None)
    assert scenario is not None
    assert scenario.kind == "negative"
    assert scenario.actor == "marek.nowak"
    assert scenario.stage == StageName.authorization
    assert scenario.expected.status == CallStatus.MASKED
    assert scenario.expected.rule_id == "resource_projection"
