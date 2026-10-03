import pytest

from control_layer.domain.models.decision import (
    Decision,
    StageResult,
    Violation,
    merge_action,
    pick_primary_violation,
    status_for,
)
from control_layer.domain.models.enums import CallStatus, RuleAction, Severity, StageName


def _violation(action: RuleAction, rule_id: str = "r1") -> Violation:
    return Violation(
        stage=StageName.policy,
        rule_id=rule_id,
        action=action,
        severity=Severity.medium,
        owasp=[],
        evidence=[],
        confidence=1.0,
    )


@pytest.mark.parametrize(
    ("actions", "expected"),
    [
        ([RuleAction.allow], RuleAction.allow),
        ([RuleAction.allow, RuleAction.flag], RuleAction.flag),
        ([RuleAction.flag, RuleAction.mask], RuleAction.mask),
        ([RuleAction.mask, RuleAction.require_approval], RuleAction.require_approval),
        ([RuleAction.require_approval, RuleAction.block], RuleAction.block),
        ([RuleAction.block, RuleAction.quarantine], RuleAction.quarantine),
        ([RuleAction.quarantine, RuleAction.block, RuleAction.allow], RuleAction.quarantine),
        ([], RuleAction.allow),
        ([RuleAction.mask, RuleAction.flag, RuleAction.allow], RuleAction.mask),
    ],
)
def test_merge_action_precedence(actions: list[RuleAction], expected: RuleAction) -> None:
    assert merge_action(actions) == expected


@pytest.mark.parametrize(
    ("action", "expected_status"),
    [
        (RuleAction.quarantine, CallStatus.BLOCKED),
        (RuleAction.block, CallStatus.BLOCKED),
        (RuleAction.require_approval, CallStatus.ESCALATED),
        (RuleAction.mask, CallStatus.MASKED),
        (RuleAction.flag, CallStatus.FLAGGED),
        (RuleAction.allow, CallStatus.ALLOWED),
    ],
)
def test_status_for_mapping(action: RuleAction, expected_status: CallStatus) -> None:
    assert status_for(action) == expected_status


def test_decision_primary_violation_picks_highest_precedence() -> None:
    violations = [
        _violation(RuleAction.flag, "flag_rule"),
        _violation(RuleAction.block, "block_rule"),
        _violation(RuleAction.mask, "mask_rule"),
    ]
    decision = Decision(
        status=CallStatus.BLOCKED,
        action=RuleAction.block,
        violations=violations,
        masked_text=None,
        approval_id=None,
        stage_results=[],
        stage_timings_ms={},
    )
    assert decision.primary_violation is not None
    assert decision.primary_violation.rule_id == "block_rule"


def test_decision_primary_violation_none_when_no_violations() -> None:
    decision = Decision(
        status=CallStatus.ALLOWED,
        action=RuleAction.allow,
        violations=[],
        masked_text=None,
        approval_id=None,
        stage_results=[],
        stage_timings_ms={},
    )
    assert decision.primary_violation is None


def test_stage_result_defaults() -> None:
    result = StageResult(stage=StageName.dlp, action=RuleAction.allow, timing_ms=1.2)
    assert result.violations == []
    assert result.cache_hit is False
    assert result.masked_text is None


def test_pick_primary_violation_standalone_matches_decision_property() -> None:
    violations = [
        _violation(RuleAction.flag, "flag_rule"),
        _violation(RuleAction.block, "block_rule"),
    ]
    assert pick_primary_violation(violations).rule_id == "block_rule"


def test_pick_primary_violation_empty_list_returns_none() -> None:
    assert pick_primary_violation([]) is None
