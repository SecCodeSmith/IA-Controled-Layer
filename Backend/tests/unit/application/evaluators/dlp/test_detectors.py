from control_layer.application.dlp.session_vault import SessionVault
from control_layer.application.evaluators.dlp.detectors import DetectorsEvaluator
from control_layer.domain.models.enums import InterceptionPoint
from tests.unit.application.evaluators.conftest import (
    FakeCacheRepository,
    make_context,
    make_identity,
    make_policy,
    make_rule,
)


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


_VAULT_PARAMS = {"vault": {"ttl_s": 60, "restore": {"email": ["mail.send"]}}}


async def test_vault_keeps_placeholders_stable_across_texts_in_a_session() -> None:
    evaluator = DetectorsEvaluator(SessionVault(FakeCacheRepository()))
    rule = make_rule(rule_type="detectors", detect=["email"], action="mask", params=_VAULT_PARAMS)
    first = make_context(
        point=InterceptionPoint.tool_result, text="a@b.pl and k@b.pl", session_id="s1"
    )
    second = make_context(point=InterceptionPoint.tool_result, text="k@b.pl", session_id="s1")

    await evaluator.evaluate(rule, first, make_policy())
    outcome = await evaluator.evaluate(rule, second, make_policy())

    assert outcome.masked_text == "[EMAIL_2]"


async def test_vault_not_used_without_vault_params_or_session() -> None:
    cache = FakeCacheRepository()
    evaluator = DetectorsEvaluator(SessionVault(cache))
    plain = make_rule(rule_type="detectors", detect=["email"], action="mask")
    vaulted = make_rule(
        rule_type="detectors", detect=["email"], action="mask", params=_VAULT_PARAMS
    )
    ctx = make_context(point=InterceptionPoint.tool_result, text="x@b.pl", session_id="s1")
    no_session = make_context(point=InterceptionPoint.tool_result, text="x@b.pl", session_id="")

    assert (await evaluator.evaluate(plain, ctx, make_policy())).masked_text == "[EMAIL_1]"
    assert (await evaluator.evaluate(vaulted, no_session, make_policy())).masked_text == (
        "[EMAIL_1]"
    )
    assert cache.store == {}


async def test_vault_only_stores_kinds_listed_in_restore() -> None:
    cache = FakeCacheRepository()
    evaluator = DetectorsEvaluator(SessionVault(cache))
    rule = make_rule(
        rule_type="detectors", detect=["email", "pesel"], action="mask", params=_VAULT_PARAMS
    )
    ctx = make_context(
        point=InterceptionPoint.tool_result, text="x@b.pl PESEL 44051401359", session_id="s1"
    )

    outcome = await evaluator.evaluate(rule, ctx, make_policy())

    assert outcome.masked_text == "[EMAIL_1] PESEL [PESEL_1]"
    assert not any("44051401359" in key or "44051401359" in v for key, v in cache.store.items())


async def test_vault_placeholders_are_scoped_to_the_caller() -> None:
    evaluator = DetectorsEvaluator(SessionVault(FakeCacheRepository()))
    rule = make_rule(rule_type="detectors", detect=["email"], action="mask", params=_VAULT_PARAMS)
    mine = make_context(point=InterceptionPoint.tool_result, text="a@b.pl", session_id="s1")
    other = make_context(
        point=InterceptionPoint.tool_result,
        text="k@b.pl",
        session_id="s1",
        identity=make_identity(sub="intruder"),
    )

    await evaluator.evaluate(rule, mine, make_policy())
    outcome = await evaluator.evaluate(rule, other, make_policy())

    assert outcome.masked_text == "[EMAIL_1]"
