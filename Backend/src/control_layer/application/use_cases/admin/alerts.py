from __future__ import annotations

from control_layer.domain.models.alert import Alert
from control_layer.domain.ports.alert_store import AlertStore

_OVERFETCH_LIMIT = 5000


class ListAlertsUseCase:
    def __init__(self, alert_store: AlertStore) -> None:
        self._alert_store = alert_store

    async def execute(
        self, limit: int = 100, user: str | None = None, rule_id: str | None = None
    ) -> list[Alert]:
        pool = await self._alert_store.list_recent(limit=max(limit, _OVERFETCH_LIMIT))
        filtered = pool
        if user is not None:
            filtered = [a for a in filtered if a.user.sub == user]
        if rule_id is not None:
            filtered = [a for a in filtered if a.rule_id == rule_id]
        return filtered[-limit:] if limit else filtered
