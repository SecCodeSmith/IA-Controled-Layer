from control_layer.application.evaluators.dlp.sequence import SequenceEvaluator
from control_layer.domain.models.session import SessionState
from tests.unit.application.evaluators.conftest import (
    make_context,
    make_descriptor,
    make_policy,
    make_rule,
)


async def test_tag_seen_before_triggers_match() -> None:
    evaluator = SequenceEvaluator()
    rule = make_rule(rule_type="sequence", match={"sequence": ["read_external", "send_external"]})
    policy = make_policy()
    session_state = SessionState(session_id="s1", tags_seen=["read_external"])
    ctx = make_context(
        metadata={
            "tool_descriptor": make_descriptor(tags=["send_external"]),
            "session_state": session_state,
        }
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.reason == "Possible exfiltration after reading external doc"


async def test_tainted_session_triggers_match_even_without_tag_history() -> None:
    evaluator = SequenceEvaluator()
    rule = make_rule(rule_type="sequence", match={"sequence": ["read_external", "send_external"]})
    policy = make_policy()
    session_state = SessionState(session_id="s1", tainted=True)
    ctx = make_context(
        metadata={
            "tool_descriptor": make_descriptor(tags=["send_external"]),
            "session_state": session_state,
        }
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True


async def test_descriptor_without_second_tag_is_not_matched() -> None:
    evaluator = SequenceEvaluator()
    rule = make_rule(rule_type="sequence", match={"sequence": ["read_external", "send_external"]})
    policy = make_policy()
    session_state = SessionState(session_id="s1", tags_seen=["read_external"])
    ctx = make_context(
        metadata={
            "tool_descriptor": make_descriptor(tags=["other_tag"]),
            "session_state": session_state,
        }
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_no_prior_tag_and_not_tainted_is_not_matched() -> None:
    evaluator = SequenceEvaluator()
    rule = make_rule(rule_type="sequence", match={"sequence": ["read_external", "send_external"]})
    policy = make_policy()
    session_state = SessionState(session_id="s1")
    ctx = make_context(
        metadata={
            "tool_descriptor": make_descriptor(tags=["send_external"]),
            "session_state": session_state,
        }
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_missing_session_state_is_not_matched() -> None:
    evaluator = SequenceEvaluator()
    rule = make_rule(rule_type="sequence", match={"sequence": ["read_external", "send_external"]})
    policy = make_policy()
    ctx = make_context(metadata={"tool_descriptor": make_descriptor(tags=["send_external"])})

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_missing_sequence_match_is_not_matched() -> None:
    evaluator = SequenceEvaluator()
    rule = make_rule(rule_type="sequence", match={})
    policy = make_policy()
    ctx = make_context(metadata={"tool_descriptor": make_descriptor(tags=["send_external"])})

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False
