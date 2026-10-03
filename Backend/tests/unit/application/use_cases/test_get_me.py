from __future__ import annotations

from datetime import UTC, datetime

from control_layer.application.use_cases.get_me import GetMeUseCase
from control_layer.domain.models.budget_usage import BudgetUsage
from control_layer.domain.models.enums import Role
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.provider import ProviderInfo
from control_layer.domain.models.risk import RiskProfile
from control_layer.domain.policy.parser import parse_policy_document


class _FakeToolCatalog:
    async def provisioned_for(self, identity):  # noqa: ANN001, ANN201
        return []

    async def descriptor(self, server, tool):  # noqa: ANN001, ANN201
        raise NotImplementedError


class _FakeBudgetRepository:
    async def get_usage(self, sub: str) -> BudgetUsage:
        return BudgetUsage(
            tokens_used=3420, tokens_limit=10000, cost_used_usd=0.0012, cost_limit_usd=1.0,
            resets_at=datetime(2026, 10, 5, tzinfo=UTC),
        )

    async def record_usage(self, sub, tokens, cost_usd):  # noqa: ANN001, ANN201
        raise NotImplementedError

    async def reset(self, sub=None):  # noqa: ANN001, ANN201
        raise NotImplementedError


class _FakeRiskRepository:
    async def get(self, sub: str) -> RiskProfile:
        return RiskProfile(sub=sub, score=12)

    async def update(self, profile):  # noqa: ANN001
        raise NotImplementedError

    async def list_all(self):  # noqa: ANN201
        raise NotImplementedError


class _FakePolicyRepository:
    def __init__(self, policy) -> None:  # noqa: ANN001
        self._policy = policy

    async def current(self):  # noqa: ANN201
        return self._policy

    async def reload(self):  # noqa: ANN201
        return self._policy

    async def status(self) -> dict:
        return {}


class _FakeModelProvider:
    async def complete(self, request):  # noqa: ANN001, ANN201
        raise NotImplementedError

    def describe(self) -> ProviderInfo:
        return ProviderInfo(name="ollama", model="qwen2.5:7b")


def _policy():
    data = {
        "version": 3,
        "profile": "balanced",
        "models": {"allowed": ["mock"], "pricing": {}},
        "roles": {},
        "locations": {},
        "rules": [],
        "budgets": {
            "per_user_tokens": 10000, "per_user_cost_usd": 1.0, "max_tokens_per_request": 2048,
            "upstream_timeout_s": 30, "warn_at_percent": 80, "on_exceeded": "block",
        },
    }
    return parse_policy_document(data, source_hash="h")


def _identity() -> Identity:
    return Identity(
        sub="anna.kowalska", name="Anna Kowalska", role=Role.developer, location="Krakow, PL",
        region="PL", agent_id="agent-anna-dev-7f3a",
    )


async def test_assembles_me_view() -> None:
    use_case = GetMeUseCase(
        _FakeToolCatalog(), _FakeBudgetRepository(), _FakeRiskRepository(),
        _FakePolicyRepository(_policy()), _FakeModelProvider(),
    )
    view = await use_case.execute(_identity())
    assert view.identity.sub == "anna.kowalska"
    assert view.policy_name == "roles.developer"
    assert view.policy_version == 3
    assert view.budget.tokens_used == 3420
    assert view.risk.score == 12
    assert view.provider.name == "ollama"
