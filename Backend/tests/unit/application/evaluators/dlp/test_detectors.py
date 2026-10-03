from control_layer.application.evaluators.dlp.detectors import DetectorsEvaluator
from control_layer.domain.models.enums import InterceptionPoint
from tests.unit.application.evaluators.conftest import make_context, make_policy, make_rule


async def test_no_detect_kinds_is_not_matched() -> None:
    evaluator = DetectorsEvaluator()
    rule = make_rule(rule_type="detectors", detect=None, action="mask")
    policy = make_policy()
    ctx = make_context(point=InterceptionPoint.response, text="nothing sensitive here")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_no_matches_in_text_is_not_matched() -> None:
    evaluator = DetectorsEvaluator()
    rule = make_rule(rule_type="detectors", detect=["email"], action="mask")
    policy = make_policy()
    ctx = make_context(point=InterceptionPoint.response, text="no contact info here")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_single_email_mask_action_produces_masked_text_and_reason() -> None:
    evaluator = DetectorsEvaluator()
    rule = make_rule(rule_type="detectors", detect=["email"], action="mask")
    policy = make_policy()
    ctx = make_context(point=InterceptionPoint.response, text="contact anna@bank.pl now")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.masked_text == "contact [EMAIL_1] now"
    assert outcome.reason == "1 email address masked in the response"


async def test_multiple_emails_pluralize_the_reason() -> None:
    evaluator = DetectorsEvaluator()
    rule = make_rule(rule_type="detectors", detect=["email"], action="mask")
    policy = make_policy()
    ctx = make_context(
        point=InterceptionPoint.response, text="cc anna@bank.pl and marek@bank.pl please"
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.reason == "2 email addresses masked in the response"


async def test_combined_kinds_join_the_reason_with_and() -> None:
    evaluator = DetectorsEvaluator()
    rule = make_rule(rule_type="detectors", detect=["email", "pesel"], action="mask")
    policy = make_policy()
    ctx = make_context(
        point=InterceptionPoint.response, text="contact anna@bank.pl, PESEL 44051401359"
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.reason == "1 email address and 1 PESEL number masked in the response"


async def test_block_action_has_no_masked_text_and_names_kinds() -> None:
    evaluator = DetectorsEvaluator()
    rule = make_rule(rule_type="detectors", detect=["pesel"], action="block")
    policy = make_policy()
    ctx = make_context(point=InterceptionPoint.tool_result, text="PESEL 44051401359 on file")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.masked_text is None
    assert outcome.reason == "1 PESEL number found in the tool_result"


async def test_evidence_lists_matched_kinds_not_raw_values() -> None:
    evaluator = DetectorsEvaluator()
    rule = make_rule(rule_type="detectors", detect=["email"], action="mask")
    policy = make_policy()
    ctx = make_context(point=InterceptionPoint.response, text="contact anna@bank.pl now")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.evidence == ["email"]
    assert "anna@bank.pl" not in outcome.evidence
