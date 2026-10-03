from __future__ import annotations

from datetime import UTC, datetime

from control_layer.domain.policy.parser import parse_policy_document
from control_layer.infrastructure.cache.in_memory_cache_repository import (
    InMemoryCacheRepository,
)
from control_layer.infrastructure.repositories.budget_repository import CacheBudgetRepository

POLICY_DICT = {
    "version": 1,
    "profile": "balanced",
    "models": {"allowed": ["mock"], "pricing": {}},
    "roles": {},
    "locations": {},
    "rules": [],
    "budgets": {
        "per_user_tokens": 10000,
        "per_user_cost_usd": 1.0,
        "max_tokens_per_request": 2048,
        "upstream_timeout_s": 30,
        "warn_at_percent": 80,
        "on_exceeded": "block",
    },
}


class _FakePolicyRepository:
    def __init__(self, document) -> None:
        self._document = document

    async def current(self):
        return self._document

    async def reload(self):
        return self._document

    async def status(self):
        return {"version": self._document.version, "status": "LOADED"}


def _policy_repository():
    document = parse_policy_document(POLICY_DICT, source_hash="abc123")
    return _FakePolicyRepository(document)


def _fixed_clock(value: datetime):
    return lambda: value


async def test_get_usage_defaults_to_zero_with_limits_from_policy() -> None:
    repo = CacheBudgetRepository(InMemoryCacheRepository(), _policy_repository())

    usage = await repo.get_usage("anna.kowalska")

    assert usage.tokens_used == 0
    assert usage.tokens_limit == 10000
    assert usage.cost_used_usd == 0.0
    assert usage.cost_limit_usd == 1.0


async def test_record_usage_accumulates() -> None:
    repo = CacheBudgetRepository(InMemoryCacheRepository(), _policy_repository())

    await repo.record_usage("anna.kowalska", tokens=100, cost_usd=0.01)
    usage = await repo.record_usage("anna.kowalska", tokens=50, cost_usd=0.005)

    assert usage.tokens_used == 150
    assert usage.cost_used_usd == 0.015


async def test_usage_is_per_user() -> None:
    repo = CacheBudgetRepository(InMemoryCacheRepository(), _policy_repository())

    await repo.record_usage("anna.kowalska", tokens=100, cost_usd=0.01)
    usage_other = await repo.get_usage("marek.nowak")

    assert usage_other.tokens_used == 0


async def test_resets_at_is_next_midnight_utc() -> None:
    clock = _fixed_clock(datetime(2026, 10, 3, 14, 30, 0, tzinfo=UTC))
    repo = CacheBudgetRepository(InMemoryCacheRepository(), _policy_repository(), clock=clock)

    usage = await repo.get_usage("anna.kowalska")

    assert usage.resets_at == datetime(2026, 10, 4, 0, 0, 0, tzinfo=UTC)


async def test_reset_single_user() -> None:
    repo = CacheBudgetRepository(InMemoryCacheRepository(), _policy_repository())
    await repo.record_usage("anna.kowalska", tokens=100, cost_usd=0.01)
    await repo.record_usage("marek.nowak", tokens=200, cost_usd=0.02)

    await repo.reset("anna.kowalska")

    assert (await repo.get_usage("anna.kowalska")).tokens_used == 0
    assert (await repo.get_usage("marek.nowak")).tokens_used == 200


async def test_reset_all_users() -> None:
    repo = CacheBudgetRepository(InMemoryCacheRepository(), _policy_repository())
    await repo.record_usage("anna.kowalska", tokens=100, cost_usd=0.01)
    await repo.record_usage("marek.nowak", tokens=200, cost_usd=0.02)

    await repo.reset()

    assert (await repo.get_usage("anna.kowalska")).tokens_used == 0
    assert (await repo.get_usage("marek.nowak")).tokens_used == 0


async def test_usage_resets_on_new_day() -> None:
    cache = InMemoryCacheRepository()
    day1_clock = _fixed_clock(datetime(2026, 10, 3, 23, 59, 0, tzinfo=UTC))
    repo_day1 = CacheBudgetRepository(cache, _policy_repository(), clock=day1_clock)
    await repo_day1.record_usage("anna.kowalska", tokens=100, cost_usd=0.01)

    day2_clock = _fixed_clock(datetime(2026, 10, 4, 0, 5, 0, tzinfo=UTC))
    repo_day2 = CacheBudgetRepository(cache, _policy_repository(), clock=day2_clock)

    usage = await repo_day2.get_usage("anna.kowalska")
    assert usage.tokens_used == 0
