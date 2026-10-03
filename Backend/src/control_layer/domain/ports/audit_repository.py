from __future__ import annotations

from typing import Any, Protocol

from control_layer.domain.models.audit import CallRecord


class AuditRepository(Protocol):
    async def append(self, record: CallRecord) -> None: ...

    async def list_recent(self, limit: int = 100) -> list[CallRecord]: ...

    async def get(self, call_id: str) -> CallRecord | None: ...

    async def clear(self) -> None: ...

    async def export_rows(self) -> list[dict[str, Any]]: ...
