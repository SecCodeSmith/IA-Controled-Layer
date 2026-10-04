from __future__ import annotations

from collections.abc import Callable

import pytest

from control_layer.application.pipeline.processing_pipeline import ProcessingPipeline
from control_layer.application.services.protection_service import ProtectionService
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import StageResult
from control_layer.domain.models.enums import (
    InterceptionPoint,
    ProtectionMode,
    Role,
    RuleAction,
    StageName,
)
from control_layer.domain.models.identity import Identity
from control_layer.infrastructure.cache.in_memory_cache_repository import InMemoryCacheRepository
from tests.unit.application.test_processing_pipeline import (
    FakeCacheRepository,
    FakePolicyRepository,
    _policy,
)

_RAW_TEXT = '{"rows":[{"id":"E-2001"},{"id":"E-2101"}]}'


def _identity(role: Role) -> Identity:
    return Identity(
        sub="u", name="U", role=role, location="Krakow", region="PL", agent_id="agent"
    )


class _EventCache(FakeCacheRepository):
    def __init__(self, events: list[str]) -> None:
        super().__init__()
        self._events = events

    async def get(self, key: str) -> str | None:
        self._events.append("cache.get")
        return await super().get(key)


class _Stage:
    def __init__(
        self,
        name: StageName,
        events: list[str],
        *,
        action: RuleAction = RuleAction.allow,
        effect: Callable[[ProcessingContext], str | None] | None = None,
    ) -> None:
        self.name = name
        self._events = events
        self._action = action
        self._effect = effect

    async def process(self, ctx: ProcessingContext, policy: object) -> StageResult:
        self._events.append(self.name.value)
        masked = self._effect(ctx) if self._effect is not None else None
        return StageResult(stage=self.name, action=self._action, timing_ms=0.0, masked_text=masked)


def _ctx() -> ProcessingContext:
    return ProcessingContext(
        identity=None,
        point=InterceptionPoint.tool_result,
        text=_RAW_TEXT,
        session_id="s1",
        call_id="c1",
    )


def _pipeline(
    events: list[str],
    cache: FakeCacheRepository | None,
    *,
    role: Role = Role.hr,
    projected: str | None = None,
    authorization_action: RuleAction = RuleAction.allow,
    protection: ProtectionService | None = None,
) -> ProcessingPipeline:
    def resolve_identity(ctx: ProcessingContext) -> None:
        ctx.identity = _identity(role)
        return None

    stages = [
        _Stage(StageName.identity, events, effect=resolve_identity),
        _Stage(
            StageName.authorization,
            events,
            action=authorization_action,
            effect=lambda ctx: projected,
        ),
        _Stage(StageName.dlp, events),
        _Stage(StageName.policy, events),
        _Stage(StageName.behavior, events),
        _Stage(StageName.resource, events),
        _Stage(StageName.audit, events),
    ]
    return ProcessingPipeline(
        stages=stages,
        cache=cache,
        policy_repository=FakePolicyRepository(_policy()),
        protection=protection,
    )


def _keys(cache: FakeCacheRepository) -> list[str]:
    return list(cache.store)


@pytest.mark.asyncio
async def test_key_is_computed_after_the_authorization_stage() -> None:
    events: list[str] = []
    cache = _EventCache(events)

    await _pipeline(events, cache).run(_ctx())

    assert events.index("cache.get") > events.index("authorization")
    assert events.index("cache.get") < events.index("dlp")


@pytest.mark.asyncio
async def test_different_projected_text_yields_different_keys() -> None:
    cache = FakeCacheRepository()

    await _pipeline([], cache, projected='{"rows":[{"id":"E-2001"}]}').run(_ctx())
    await _pipeline([], cache, projected='{"rows":[{"id":"E-2101"}]}').run(_ctx())

    assert len(_keys(cache)) == 2


@pytest.mark.asyncio
async def test_different_projection_is_not_served_from_the_other_cache_entry() -> None:
    cache = FakeCacheRepository()
    first_events: list[str] = []
    second_events: list[str] = []

    await _pipeline(first_events, cache, projected='{"rows":[1]}').run(_ctx())
    await _pipeline(second_events, cache, projected='{"rows":[2]}').run(_ctx())

    assert "dlp" in second_events
    assert "policy" in second_events


@pytest.mark.asyncio
async def test_different_roles_with_identical_text_yield_different_keys() -> None:
    cache = FakeCacheRepository()

    await _pipeline([], cache, role=Role.hr).run(_ctx())
    await _pipeline([], cache, role=Role.developer).run(_ctx())

    assert len(_keys(cache)) == 2


@pytest.mark.asyncio
async def test_identical_role_and_projected_text_share_one_key() -> None:
    cache = FakeCacheRepository()
    events: list[str] = []

    await _pipeline([], cache, projected="same").run(_ctx())
    decision = await _pipeline(events, cache, projected="same").run(_ctx())

    assert len(_keys(cache)) == 1
    assert "dlp" not in events
    assert "policy" not in events
    assert {r.stage for r in decision.stage_results if r.cache_hit} == {
        StageName.dlp,
        StageName.policy,
    }


@pytest.mark.asyncio
async def test_cache_is_not_consulted_when_authorization_short_circuits() -> None:
    events: list[str] = []
    cache = _EventCache(events)

    await _pipeline(events, cache, authorization_action=RuleAction.block).run(_ctx())

    assert "cache.get" not in events
    assert cache.store == {}


@pytest.mark.asyncio
async def test_off_mode_stays_uncached() -> None:
    backing = InMemoryCacheRepository()
    protection = ProtectionService(backing)
    await protection.set_mode(ProtectionMode.off)
    events: list[str] = []
    cache = _EventCache(events)

    await _pipeline(events, cache, protection=protection).run(_ctx())

    assert "cache.get" not in events
    assert cache.store == {}
