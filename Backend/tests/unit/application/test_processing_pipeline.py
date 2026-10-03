from __future__ import annotations

import json

import pytest

from control_layer.application.pipeline.processing_pipeline import ProcessingPipeline
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import StageResult
from control_layer.domain.models.enums import InterceptionPoint, RuleAction, StageName
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.policy.parser import parse_policy_document


def _policy(version: int = 1) -> PolicyDocument:
    data = {
        "version": version,
        "profile": "balanced",
        "models": {"allowed": ["mock"], "pricing": {}},
        "roles": {"developer": {"mcp_servers": ["github"]}},
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
    return parse_policy_document(data, source_hash=f"hash-{version}")


class FakePolicyRepository:
    def __init__(self, document: PolicyDocument) -> None:
        self.document = document

    async def current(self) -> PolicyDocument:
        return self.document

    async def reload(self) -> PolicyDocument:
        return self.document

    async def status(self) -> dict:
        return {"version": self.document.version}


class FakeCacheRepository:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.set_calls: list[str] = []
        self.get_calls: list[str] = []

    async def get(self, key: str) -> str | None:
        self.get_calls.append(key)
        return self.store.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        self.set_calls.append(key)
        self.store[key] = value

    async def incr(self, key: str, ttl: int | None = None) -> int:
        current = int(self.store.get(key, "0")) + 1
        self.store[key] = str(current)
        return current

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)

    async def ping(self) -> bool:
        return True

    async def keys(self, prefix: str) -> list[str]:
        return [k for k in self.store if k.startswith(prefix)]

    async def flush(self, prefix: str) -> None:
        for key in list(self.store):
            if key.startswith(prefix):
                del self.store[key]


class ScriptedStage:
    def __init__(
        self,
        name: StageName,
        calls: list[StageName],
        action: RuleAction = RuleAction.allow,
        masked_text: str | None = None,
        approval_id: str | None = None,
        text_log: list[str] | None = None,
    ) -> None:
        self.name = name
        self._calls = calls
        self._action = action
        self._masked_text = masked_text
        self._approval_id = approval_id
        self._text_log = text_log

    async def process(self, ctx: ProcessingContext, policy: PolicyDocument) -> StageResult:
        self._calls.append(self.name)
        if self._text_log is not None:
            self._text_log.append(ctx.current_text)
        return StageResult(
            stage=self.name,
            action=self._action,
            timing_ms=0.0,
            masked_text=self._masked_text,
            approval_id=self._approval_id,
        )


def _ctx(
    text: str = "hello world", point: InterceptionPoint = InterceptionPoint.prompt
) -> ProcessingContext:
    return ProcessingContext(
        identity=None,
        point=point,
        text=text,
        session_id="s1",
        call_id="c1",
    )


def _full_stage_set(
    calls: list[StageName], text_log: dict[StageName, list[str]] | None = None
) -> list[ScriptedStage]:
    text_log = text_log or {}
    return [
        ScriptedStage(name, calls, text_log=text_log.get(name))
        for name in StageName.ordered()
    ]


def test_constructor_rejects_duplicate_stage_names() -> None:
    calls: list[StageName] = []
    stages = [
        ScriptedStage(StageName.identity, calls),
        ScriptedStage(StageName.identity, calls),
    ]
    with pytest.raises(ValueError):
        ProcessingPipeline(
            stages=stages, cache=None, policy_repository=FakePolicyRepository(_policy())
        )


def test_constructor_rejects_out_of_order_stages() -> None:
    calls: list[StageName] = []
    stages = [
        ScriptedStage(StageName.authorization, calls),
        ScriptedStage(StageName.identity, calls),
    ]
    with pytest.raises(ValueError):
        ProcessingPipeline(
            stages=stages, cache=None, policy_repository=FakePolicyRepository(_policy())
        )


def test_constructor_accepts_correctly_ordered_subset() -> None:
    calls: list[StageName] = []
    stages = [
        ScriptedStage(StageName.identity, calls),
        ScriptedStage(StageName.dlp, calls),
        ScriptedStage(StageName.audit, calls),
    ]
    ProcessingPipeline(
        stages=stages, cache=None, policy_repository=FakePolicyRepository(_policy())
    )


@pytest.mark.asyncio
async def test_stages_run_in_order_and_record_timing() -> None:
    calls: list[StageName] = []
    stages = _full_stage_set(calls)
    pipeline = ProcessingPipeline(
        stages=stages, cache=None, policy_repository=FakePolicyRepository(_policy())
    )

    decision = await pipeline.run(_ctx())

    assert calls == StageName.ordered()
    assert set(decision.stage_timings_ms) == {s.value for s in StageName.ordered()}
    for timing in decision.stage_timings_ms.values():
        assert isinstance(timing, float)
        assert timing >= 0.0


@pytest.mark.asyncio
async def test_short_circuit_on_block_stops_later_non_audit_stages_but_audit_still_runs() -> None:
    calls: list[StageName] = []
    stages = [
        ScriptedStage(StageName.identity, calls),
        ScriptedStage(StageName.authorization, calls, action=RuleAction.block),
        ScriptedStage(StageName.dlp, calls),
        ScriptedStage(StageName.policy, calls),
        ScriptedStage(StageName.behavior, calls),
        ScriptedStage(StageName.resource, calls),
        ScriptedStage(StageName.audit, calls),
    ]
    pipeline = ProcessingPipeline(
        stages=stages, cache=None, policy_repository=FakePolicyRepository(_policy())
    )

    decision = await pipeline.run(_ctx())

    assert calls == [StageName.identity, StageName.authorization, StageName.audit]
    assert decision.status.value == "BLOCKED"


@pytest.mark.asyncio
async def test_masked_text_from_earlier_stage_visible_to_later_stages() -> None:
    calls: list[StageName] = []
    policy_text_log: list[str] = []
    stages = [
        ScriptedStage(StageName.identity, calls),
        ScriptedStage(StageName.authorization, calls),
        ScriptedStage(StageName.dlp, calls, masked_text="[EMAIL_1] said hi"),
        ScriptedStage(StageName.policy, calls, text_log=policy_text_log),
        ScriptedStage(StageName.behavior, calls),
        ScriptedStage(StageName.resource, calls),
        ScriptedStage(StageName.audit, calls),
    ]
    pipeline = ProcessingPipeline(
        stages=stages, cache=None, policy_repository=FakePolicyRepository(_policy())
    )

    decision = await pipeline.run(_ctx(text="original@example.com said hi"))

    assert policy_text_log == ["[EMAIL_1] said hi"]
    assert decision.masked_text == "[EMAIL_1] said hi"


@pytest.mark.asyncio
async def test_cache_hit_skips_cacheable_stages_and_marks_cache_hit() -> None:
    calls: list[StageName] = []
    cache = FakeCacheRepository()
    policy_repo = FakePolicyRepository(_policy(version=1))
    pipeline = ProcessingPipeline(
        stages=_full_stage_set(calls), cache=cache, policy_repository=policy_repo
    )

    first_decision = await pipeline.run(_ctx(text="same text"))
    assert calls == StageName.ordered()
    assert cache.set_calls, "cache miss should populate the cache"
    assert not any(r.cache_hit for r in first_decision.stage_results)

    calls.clear()
    second_decision = await pipeline.run(_ctx(text="same text"))

    assert StageName.dlp not in calls
    assert StageName.policy not in calls
    non_cacheable_stage_names = (
        StageName.identity,
        StageName.authorization,
        StageName.behavior,
        StageName.resource,
        StageName.audit,
    )
    for stage_name in non_cacheable_stage_names:
        assert stage_name in calls

    cache_hit_stages = {r.stage for r in second_decision.stage_results if r.cache_hit}
    assert cache_hit_stages == {StageName.dlp, StageName.policy}


@pytest.mark.asyncio
async def test_policy_version_change_produces_new_cache_key() -> None:
    calls: list[StageName] = []
    cache = FakeCacheRepository()
    policy_repo = FakePolicyRepository(_policy(version=1))
    pipeline = ProcessingPipeline(
        stages=_full_stage_set(calls), cache=cache, policy_repository=policy_repo
    )

    await pipeline.run(_ctx(text="same text"))
    assert StageName.dlp in calls and StageName.policy in calls

    policy_repo.document = _policy(version=2)
    calls.clear()
    await pipeline.run(_ctx(text="same text"))

    assert StageName.dlp in calls
    assert StageName.policy in calls


@pytest.mark.asyncio
async def test_cache_is_none_means_no_caching() -> None:
    calls: list[StageName] = []
    pipeline = ProcessingPipeline(
        stages=_full_stage_set(calls), cache=None, policy_repository=FakePolicyRepository(_policy())
    )

    await pipeline.run(_ctx(text="same text"))
    calls.clear()
    await pipeline.run(_ctx(text="same text"))

    assert StageName.dlp in calls
    assert StageName.policy in calls


@pytest.mark.asyncio
async def test_cache_payload_is_json_serializable_stage_results() -> None:
    calls: list[StageName] = []
    cache = FakeCacheRepository()
    pipeline = ProcessingPipeline(
        stages=_full_stage_set(calls),
        cache=cache,
        policy_repository=FakePolicyRepository(_policy()),
    )

    await pipeline.run(_ctx(text="same text"))

    assert len(cache.set_calls) == 1
    stored = json.loads(cache.store[cache.set_calls[0]])
    assert {item["stage"] for item in stored} == {"dlp", "policy"}
