from __future__ import annotations

from datetime import UTC, datetime

from control_layer.application.services.budget_service import BudgetService
from control_layer.domain.models.budget_usage import BudgetUsage
from control_layer.domain.models.chat import Usage
from control_layer.domain.models.enums import Role
from control_layer.domain.models.identity import Identity
from control_layer.domain.policy.parser import parse_policy_document


class _FakeBudgetRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, float]] = []

    async def get_usage(self, sub: str) -> BudgetUsage:
        raise NotImplementedError

    async def record_usage(self, sub: str, tokens: int, cost_usd: float) -> BudgetUsage:
        self.calls.append((sub, tokens, cost_usd))
        return BudgetUsage(
            tokens_used=tokens,
            tokens_limit=10000,
            cost_used_usd=cost_usd,
            cost_limit_usd=1.0,
            resets_at=datetime(2026, 10, 5, tzinfo=UTC),
        )

    async def reset(self, sub: str | None = None) -> None:
        raise NotImplementedError


def _policy(pricing: dict):  # noqa: ANN001
    data = {
        "version": 1,
        "profile": "balanced",
        "models": {"allowed": list(pricing), "pricing": pricing},
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
    return parse_policy_document(data, source_hash="h")


def _identity() -> Identity:
    return Identity(
        sub="anna.kowalska",
        name="Anna Kowalska",
        role=Role.developer,
        location="Krakow, PL",
        region="PL",
        agent_id="agent-anna-dev-7f3a",
    )


async def test_computes_cost_from_pricing_table() -> None:
    repo = _FakeBudgetRepository()
    service = BudgetService(repo)
    pricing = {"qwen2.5:7b": {"input_per_1k_usd": 0.0002, "output_per_1k_usd": 0.0004}}
    usage = Usage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)
    await service.record(_identity(), usage, "qwen2.5:7b", _policy(pricing))
    sub, tokens, cost = repo.calls[0]
    assert sub == "anna.kowalska"
    assert tokens == 1500
    assert cost == 1000 / 1000 * 0.0002 + 500 / 1000 * 0.0004


async def test_cost_is_zero_when_model_pricing_missing() -> None:
    repo = _FakeBudgetRepository()
    service = BudgetService(repo)
    usage = Usage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)
    await service.record(_identity(), usage, "unknown-model", _policy({}))
    _, _, cost = repo.calls[0]
    assert cost == 0.0
