from __future__ import annotations

from control_layer.application.pipeline.stages.audit import AuditStage
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.enums import InterceptionPoint, RuleAction, StageName
from control_layer.domain.policy.parser import parse_policy_document


class _FakeEventPublisher:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []

    async def publish(self, event: str, data: dict) -> None:
        self.published.append((event, data))


def _policy():
    data = {
        "version": 1,
        "profile": "balanced",
        "models": {"allowed": ["mock"], "pricing": {}},
        "roles": {},
        "locations": {},
        "rules": [],
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


async def test_publishes_stage_trace_event_and_allows() -> None:
    publisher = _FakeEventPublisher()
    stage = AuditStage(publisher)
    ctx = ProcessingContext(
        identity=None,
        point=InterceptionPoint.prompt,
        text="hi",
        session_id="s1",
        call_id="c_000042",
        metadata={"stage_timings": {"identity": 0.1, "dlp": 1.2}},
    )
    result = await stage.process(ctx, _policy())
    assert result.action == RuleAction.allow
    assert publisher.published == [
        ("stage_trace", {"call_id": "c_000042", "point": "prompt", "stages": {"identity": 0.1, "dlp": 1.2}})
    ]


async def test_publishes_empty_stages_when_not_tracked() -> None:
    publisher = _FakeEventPublisher()
    stage = AuditStage(publisher)
    ctx = ProcessingContext(
        identity=None, point=InterceptionPoint.tool_call, text="{}", session_id="s1", call_id="c_1"
    )
    await stage.process(ctx, _policy())
    assert publisher.published[0][1]["stages"] == {}


def test_stage_name_is_audit() -> None:
    assert AuditStage(_FakeEventPublisher()).name == StageName.audit
