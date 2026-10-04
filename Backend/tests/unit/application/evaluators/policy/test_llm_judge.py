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


async def test_prompt_treats_security_education_as_benign_and_keeps_json_contract() -> None:
    class CapturingProvider(FakeModelProvider):
        captured = None

        async def complete(self, request):
            CapturingProvider.captured = request
            return await super().complete(request)

    provider = CapturingProvider(content=json.dumps({"verdict": "allow", "reason": "ok"}))
    evaluator = LlmJudgeEvaluator(provider, model="qwen2.5:7b")

    await evaluator.evaluate(
        make_rule(rule_type="llm_judge"),
        make_context(text="Explain what prompt injection is"),
        make_policy(),
    )

    system = CapturingProvider.captured.messages[0].content
    assert "educational material on security topics" in system
    assert "alter the assistant's instructions" in system
    assert "extract the system prompt" in system
    assert "developer how-to questions" in system
    assert '{"verdict": "allow|flag|block"' in system
    assert CapturingProvider.captured.response_format == {"type": "json_object"}


async def _judge(payload: dict, params: dict | None = None):
    provider = FakeModelProvider(content=json.dumps(payload))
    evaluator = LlmJudgeEvaluator(provider, model="qwen2.5:7b")
    rule = make_rule(rule_type="llm_judge", params=params or {})
    return await evaluator.evaluate(rule, make_context(text="hello"), make_policy())


async def test_block_below_default_block_confidence_is_inconclusive() -> None:
    outcome = await _judge({"verdict": "block", "confidence": 0.69, "reason": "maybe"})

    assert outcome.matched is True
    assert outcome.inconclusive is True
    assert outcome.confidence == 0.69
    assert "maybe" in (outcome.reason or "")


async def test_block_at_default_block_confidence_is_a_confident_match() -> None:
    outcome = await _judge({"verdict": "block", "confidence": 0.7, "reason": "injection"})

    assert outcome.matched is True
    assert outcome.inconclusive is False


async def test_block_confidence_param_overrides_the_default() -> None:
    strict = await _judge(
        {"verdict": "block", "confidence": 0.8, "reason": "x"}, {"block_confidence": 0.9}
    )
    lenient = await _judge(
        {"verdict": "block", "confidence": 0.3, "reason": "x"}, {"block_confidence": 0.2}
    )

    assert strict.inconclusive is True
    assert lenient.inconclusive is False


async def test_block_without_confidence_is_confident() -> None:
    outcome = await _judge({"verdict": "block", "reason": "injection"})

    assert outcome.inconclusive is False
    assert outcome.confidence == 1.0


async def test_flag_verdict_is_always_inconclusive_even_when_confident() -> None:
    outcome = await _judge({"verdict": "flag", "confidence": 0.99, "reason": "odd"})

    assert outcome.matched is True
    assert outcome.inconclusive is True


async def test_non_numeric_confidence_is_a_fail_safe_inconclusive_flag() -> None:
    outcome = await _judge({"verdict": "block", "confidence": "high", "reason": "x"})

    assert outcome.matched is True
    assert outcome.inconclusive is True
