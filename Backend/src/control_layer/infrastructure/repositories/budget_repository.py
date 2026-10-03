from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol

from control_layer.domain.models.budget_usage import BudgetUsage
from control_layer.domain.models.policy import PolicyDocument


class _Cache(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl: float | None = None) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def flush(self, prefix: str) -> None: ...


class _PolicyRepository(Protocol):
    async def current(self) -> PolicyDocument: ...


class CacheBudgetRepository:
    _PREFIX = "budget:"

    def __init__(
        self,
        cache: _Cache,
        policy_repository: _PolicyRepository,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._cache = cache
        self._policy_repository = policy_repository
        self._clock = clock

    def _today(self) -> str:
        return self._clock().strftime("%Y-%m-%d")

    def _key(self, sub: str, day: str) -> str:
        return f"{self._PREFIX}{sub}:{day}"

    def _next_midnight_utc(self) -> datetime:
        now = self._clock()
        start_of_today = datetime(now.year, now.month, now.day, tzinfo=UTC)
        return start_of_today + timedelta(days=1)

    async def _read_raw(self, sub: str) -> tuple[int, float]:
        raw = await self._cache.get(self._key(sub, self._today()))
        if raw is None:
            return 0, 0.0
        data = json.loads(raw)
        return data.get("tokens_used", 0), data.get("cost_used_usd", 0.0)

    async def get_usage(self, sub: str) -> BudgetUsage:
        policy = await self._policy_repository.current()
        tokens_used, cost_used = await self._read_raw(sub)
        return BudgetUsage(
            tokens_used=tokens_used,
            tokens_limit=policy.budgets.per_user_tokens,
            cost_used_usd=cost_used,
            cost_limit_usd=policy.budgets.per_user_cost_usd,
            resets_at=self._next_midnight_utc(),
        )

    async def record_usage(self, sub: str, tokens: int, cost_usd: float) -> BudgetUsage:
        tokens_used, cost_used = await self._read_raw(sub)
        tokens_used += tokens
        cost_used += cost_usd
        ttl = int((self._next_midnight_utc() - self._clock()).total_seconds()) + 60
        await self._cache.set(
            self._key(sub, self._today()),
            json.dumps({"tokens_used": tokens_used, "cost_used_usd": cost_used}),
            ttl=ttl,
        )
        return await self.get_usage(sub)

    async def reset(self, sub: str | None = None) -> None:
        if sub is None:
            await self._cache.flush(self._PREFIX)
        else:
            await self._cache.delete(self._key(sub, self._today()))
