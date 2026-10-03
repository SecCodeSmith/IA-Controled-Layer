import json

from control_layer.application.evaluators.policy.llm_judge import LlmJudgeEvaluator
from tests.unit.application.evaluators.conftest import (
    FakeModelProvider,
    HangingModelProvider,
    make_context,
    make_policy,
    make_rule,
)


async def test_allow_verdict_is_not_matched() -> None:
    provider = FakeModelProvider(content=json.dumps({"verdict": "allow", "reason": "looks fine"}))
    evaluator = LlmJudgeEvaluator(provider, model="qwen2.5:7b")
    rule = make_rule(rule_type="llm_judge")
    policy = make_policy()
    ctx = make_context(text="hello")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False
    assert outcome.reason == "looks fine"


async def test_flag_verdict_is_matched_with_half_confidence() -> None:
    provider = FakeModelProvider(content=json.dumps({"verdict": "flag", "reason": "suspicious"}))
    evaluator = LlmJudgeEvaluator(provider, model="qwen2.5:7b")
    rule = make_rule(rule_type="llm_judge")
    policy = make_policy()
    ctx = make_context(text="hello")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.confidence == 0.5
    assert outcome.reason == "suspicious"


async def test_block_verdict_is_matched_with_full_confidence() -> None:
    provider = FakeModelProvider(content=json.dumps({"verdict": "block", "reason": "malicious"}))
    evaluator = LlmJudgeEvaluator(provider, model="qwen2.5:7b")
    rule = make_rule(rule_type="llm_judge")
    policy = make_policy()
    ctx = make_context(text="hello")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.confidence == 1.0
    assert outcome.reason == "malicious"


async def test_timeout_is_a_fail_safe_inconclusive_flag() -> None:
    provider = HangingModelProvider(delay_s=1.0)
    evaluator = LlmJudgeEvaluator(provider, model="qwen2.5:7b")
    rule = make_rule(rule_type="llm_judge", params={"timeout_s": 0.05})
    policy = make_policy()
    ctx = make_context(text="hello")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.confidence == 0.5
    assert outcome.inconclusive is True
    assert outcome.reason == "Judge unavailable, flagged for review"


async def test_provider_error_is_a_fail_safe_inconclusive_flag() -> None:
    provider = FakeModelProvider(error=RuntimeError("upstream down"))
    evaluator = LlmJudgeEvaluator(provider, model="qwen2.5:7b")
    rule = make_rule(rule_type="llm_judge")
    policy = make_policy()
    ctx = make_context(text="hello")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.confidence == 0.5
    assert outcome.inconclusive is True
    assert outcome.reason == "Judge unavailable, flagged for review"


async def test_unparseable_response_is_a_fail_safe_inconclusive_flag() -> None:
    provider = FakeModelProvider(content="not valid json")
    evaluator = LlmJudgeEvaluator(provider, model="qwen2.5:7b")
    rule = make_rule(rule_type="llm_judge")
    policy = make_policy()
    ctx = make_context(text="hello")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.confidence == 0.5
    assert outcome.inconclusive is True


async def test_unknown_verdict_is_a_fail_safe_inconclusive_flag() -> None:
    provider = FakeModelProvider(content=json.dumps({"verdict": "maybe", "reason": "unclear"}))
    evaluator = LlmJudgeEvaluator(provider, model="qwen2.5:7b")
    rule = make_rule(rule_type="llm_judge")
    policy = make_policy()
    ctx = make_context(text="hello")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.inconclusive is True


async def test_verdict_is_read_case_insensitively() -> None:
    provider = FakeModelProvider(content=json.dumps({"verdict": "BLOCK", "reason": "malicious"}))
    evaluator = LlmJudgeEvaluator(provider, model="qwen2.5:7b")
    rule = make_rule(rule_type="llm_judge")
    policy = make_policy()
    ctx = make_context(text="hello")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.confidence == 1.0


async def test_reasoning_key_is_used_when_reason_is_absent() -> None:
    provider = FakeModelProvider(
        content=json.dumps({"verdict": "flag", "reasoning": "looks suspicious"})
    )
    evaluator = LlmJudgeEvaluator(provider, model="qwen2.5:7b")
    rule = make_rule(rule_type="llm_judge")
    policy = make_policy()
    ctx = make_context(text="hello")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.reason == "looks suspicious"


async def test_explicit_confidence_overrides_the_default() -> None:
    provider = FakeModelProvider(
        content=json.dumps({"verdict": "flag", "reasoning": "unsure", "confidence": 0.77})
    )
    evaluator = LlmJudgeEvaluator(provider, model="qwen2.5:7b")
    rule = make_rule(rule_type="llm_judge")
    policy = make_policy()
    ctx = make_context(text="hello")

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.confidence == 0.77


async def test_rule_params_model_override_is_sent_to_provider() -> None:
    seen_models: list[str] = []

    class RecordingProvider(FakeModelProvider):
        async def complete(self, request):
            seen_models.append(request.model)
            return await super().complete(request)

    provider = RecordingProvider(content=json.dumps({"verdict": "allow", "reason": "ok"}))
    evaluator = LlmJudgeEvaluator(provider, model="default-model")
    rule = make_rule(rule_type="llm_judge", params={"model": "qwen2.5:7b"})
    policy = make_policy()
    ctx = make_context(text="hello")

    await evaluator.evaluate(rule, ctx, policy)

    assert seen_models == ["qwen2.5:7b"]
