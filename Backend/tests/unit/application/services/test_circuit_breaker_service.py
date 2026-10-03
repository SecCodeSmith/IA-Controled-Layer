from __future__ import annotations

from control_layer.application.services.circuit_breaker_service import CircuitBreakerService
from control_layer.domain.models.enums import Role, Severity
from control_layer.domain.models.identity import Identity
from control_layer.domain.policy.parser import parse_policy_document


class _FakeCache:
    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self.sets: dict[str, tuple[str, int | None]] = {}

    async def get(self, key: str) -> str | None:
        return None

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        self.sets[key] = (value, ttl)

    async def incr(self, key: str, ttl: int | None = None) -> int:
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]

    async def delete(self, key: str) -> None:
        self._counters.pop(key, None)

    async def ping(self) -> bool:
        return True

    async def keys(self, prefix: str) -> list[str]:
        return []

    async def flush(self, prefix: str) -> None:
        pass


class _FakeAlertSink:
    def __init__(self) -> None:
        self.emitted = []

    async def emit(self, alert) -> None:  # noqa: ANN001
        self.emitted.append(alert)


class _FakePolicyRepository:
    def __init__(self, policy) -> None:  # noqa: ANN001
        self._policy = policy

    async def current(self):  # noqa: ANN201
        return self._policy

    async def reload(self):  # noqa: ANN201
        return self._policy

    async def status(self) -> dict:
        return {}


def _policy(blocks: int = 5, window_s: int = 300):  # noqa: ANN001
    data = {
        "version": 1,
        "profile": "balanced",
        "models": {"allowed": ["mock"], "pricing": {}},
        "roles": {},
        "locations": {},
        "rules": [
            {
                "id": "circuit_breaker",
                "blocks": blocks,
                "window_s": window_s,
                "action": "quarantine",
                "owasp": ["ASI10"],
            }
        ],
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


def _identity() -> Identity:
    return Identity(
        sub="anna.kowalska",
        name="Anna Kowalska",
        role=Role.developer,
        location="Krakow, PL",
        region="PL",
        agent_id="agent-anna-dev-7f3a",
    )


async def test_no_alert_before_threshold() -> None:
    cache = _FakeCache()
    alert_sink = _FakeAlertSink()
    service = CircuitBreakerService(cache, alert_sink, _FakePolicyRepository(_policy(blocks=5)))
    for _ in range(4):
        await service.record_block(_identity(), "c_1")
    assert alert_sink.emitted == []
    assert "quarantine:anna.kowalska" not in cache.sets


async def test_quarantines_and_emits_critical_alert_at_threshold() -> None:
    cache = _FakeCache()
    alert_sink = _FakeAlertSink()
    service = CircuitBreakerService(cache, alert_sink, _FakePolicyRepository(_policy(blocks=3)))
    for _ in range(3):
        await service.record_block(_identity(), "c_1")
    assert "quarantine:anna.kowalska" in cache.sets
    assert len(alert_sink.emitted) == 1
    alert = alert_sink.emitted[0]
    assert alert.severity == Severity.critical
    assert alert.rule_id == "circuit_breaker"
    assert alert.reason == "User quarantined after repeated blocked actions"


async def test_stays_quarantined_and_keeps_emitting_past_threshold() -> None:
    cache = _FakeCache()
    alert_sink = _FakeAlertSink()
    service = CircuitBreakerService(cache, alert_sink, _FakePolicyRepository(_policy(blocks=2)))
    for _ in range(4):
        await service.record_block(_identity(), "c_1")
    assert len(alert_sink.emitted) == 3
