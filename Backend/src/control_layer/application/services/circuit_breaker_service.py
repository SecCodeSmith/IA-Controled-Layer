from __future__ import annotations

import secrets
from collections.abc import Callable
from datetime import UTC, datetime

from control_layer.domain.models.alert import Alert, AlertUserRef
from control_layer.domain.models.enums import CallStatus, Severity, StageName
from control_layer.domain.models.identity import Identity
from control_layer.domain.ports.alert_sink import AlertSink
from control_layer.domain.ports.cache_repository import CacheRepository
from control_layer.domain.ports.policy_repository import PolicyRepository

_RULE_ID = "circuit_breaker"
_DEFAULT_BLOCKS = 5
_DEFAULT_WINDOW_S = 300


class CircuitBreakerService:
    def __init__(
        self,
        cache: CacheRepository,
        alert_sink: AlertSink,
        policy_repository: PolicyRepository,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._cache = cache
        self._alert_sink = alert_sink
        self._policy_repository = policy_repository
        self._clock = clock

    async def record_block(self, identity: Identity, call_id: str) -> None:
        policy = await self._policy_repository.current()
        rule = next((r for r in policy.rules if r.id == _RULE_ID), None)
        window_s = rule.params.get("window_s", _DEFAULT_WINDOW_S) if rule else _DEFAULT_WINDOW_S
        blocks_threshold = rule.params.get("blocks", _DEFAULT_BLOCKS) if rule else _DEFAULT_BLOCKS
        owasp = rule.owasp if rule else []

        count = await self._cache.incr(f"cb:{identity.sub}", ttl=window_s)
        if count < blocks_threshold:
            return

        await self._cache.set(f"quarantine:{identity.sub}", "1", ttl=window_s)
        alert = Alert(
            id="al_" + secrets.token_hex(6),
            created_at=self._clock(),
            call_id=call_id,
            user=AlertUserRef(sub=identity.sub, name=identity.name, role=identity.role),
            status=CallStatus.BLOCKED,
            stage=StageName.behavior,
            rule_id=_RULE_ID,
            severity=Severity.critical,
            owasp=owasp,
            reason="User quarantined after repeated blocked actions",
            evidence=[],
        )
        await self._alert_sink.emit(alert)
