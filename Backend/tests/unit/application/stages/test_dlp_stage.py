from __future__ import annotations

from control_layer.application.pipeline.stages.dlp import DlpStage
from control_layer.application.rules.registry import EvaluatorRegistry
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.enums import InterceptionPoint, RuleAction, StageName
from control_layer.domain.policy.parser import parse_policy_document


class _MaskingEvaluator:
    def __init__(self, masked_text: str) -> None:
        self._masked_text = masked_text
        self.seen_texts: list[str] = []

    async def evaluate(self, rule, ctx, policy):  # noqa: ANN001
        self.seen_texts.append(ctx.current_text)
        return RuleOutcome(matched=True, masked_text=self._masked_text, reason="masked")


def _policy(rules: list[dict]):
    data = {
        "version": 1,
        "profile": "balanced",
        "models": {"allowed": ["mock"], "pricing": {}},
        "roles": {},
        "locations": {},
        "rules": rules,
        "budgets": {
            "per_user_tokens": 1000,
            "per_user_cost_usd": 1.0,
            "max_tokens_per_request": 100,
            "upstream_timeout_s": 30,
            "warn_at_percent": 80,
            "on_exceeded": "block",
        },
    }
    return parse_policy_document(data, source_hash="h")


def _ctx() -> ProcessingContext:
    return ProcessingContext(
        identity=None,
        point=InterceptionPoint.response,
        text="t.lis@example.com called twice",
        session_id="s1",
        call_id="c1",
    )


async def test_masked_text_accumulates_across_two_detectors() -> None:
    registry = EvaluatorRegistry()
    first = _MaskingEvaluator("[EMAIL_1] called twice")
    second = _MaskingEvaluator("[EMAIL_1] called [NUM_1] times")
    registry.register("pii", first)
    registry.register("secrets", second)
    stage = DlpStage(registry)
    rules = [
        {"id": "pii_masking", "on": "response", "type": "pii", "stage": "dlp", "action": "mask"},
        {"id": "secrets_detection", "on": "response", "type": "secrets", "stage": "dlp", "action": "mask"},
    ]
    ctx = _ctx()
    result = await stage.process(ctx, _policy(rules))
    assert first.seen_texts == ["t.lis@example.com called twice"]
    assert second.seen_texts == ["[EMAIL_1] called twice"]
    assert result.masked_text == "[EMAIL_1] called [NUM_1] times"
    assert result.action == RuleAction.mask


def test_stage_name_is_dlp() -> None:
    assert DlpStage(EvaluatorRegistry()).name == StageName.dlp
