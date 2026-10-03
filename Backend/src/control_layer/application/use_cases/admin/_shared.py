from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from control_layer.domain.models.audit import CallRecord
from control_layer.domain.ports.audit_repository import AuditRepository

_PERIOD_DELTAS: dict[str, timedelta] = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}


async def load_all_call_records(audit_repository: AuditRepository) -> list[CallRecord]:
    rows = await audit_repository.export_rows()
    return [CallRecord.model_validate(row) for row in rows]


def filter_by_period[T](
    records: list[T],
    period: str,
    *,
    key: Callable[[T], datetime] = lambda r: r.timestamp,
    now: datetime | None = None,
) -> list[T]:
    if period == "all":
        return list(records)
    delta = _PERIOD_DELTAS.get(period)
    if delta is None:
        raise ValueError(f"unknown report period: {period!r}")
    cutoff = (now or datetime.now(UTC)) - delta
    return [r for r in records if _as_aware(key(r)) >= cutoff]


def _as_aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
