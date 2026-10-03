from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from control_layer.domain.models.audit import CallRecord

logger = logging.getLogger(__name__)

_DECISION_FILTERS = ("status", "stage", "rule_id")


class JsonlAuditRepository:
    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._records: list[CallRecord] = []
        self._lock = asyncio.Lock()
        self._load_existing()

    def _load_existing(self) -> None:
        if not self._path.exists():
            return
        with self._path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    self._records.append(CallRecord.model_validate_json(line))
                except ValidationError as exc:
                    logger.warning("Skipping invalid audit line in %s: %s", self._path, exc)

    def _append_line_sync(self, record: CallRecord) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(record.model_dump_json() + "\n")

    def _truncate_sync(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text("", encoding="utf-8")

    async def append(self, record: CallRecord) -> None:
        async with self._lock:
            self._records.append(record)
            await asyncio.to_thread(self._append_line_sync, record)

    @staticmethod
    def _matches(record: CallRecord, key: str, value: Any) -> bool:
        if key == "user":
            return record.identity.sub == value
        if key in _DECISION_FILTERS:
            return getattr(record.decision, key) == value
        return getattr(record, key, None) == value

    async def list_recent(self, limit: int = 100, **filters: Any) -> list[CallRecord]:
        items = list(reversed(self._records))
        for key, value in filters.items():
            if value is None:
                continue
            items = [record for record in items if self._matches(record, key, value)]
        return items[:limit]

    async def get(self, call_id: str) -> CallRecord | None:
        for record in reversed(self._records):
            if record.call_id == call_id:
                return record
        return None

    async def clear(self) -> None:
        async with self._lock:
            self._records.clear()
            await asyncio.to_thread(self._truncate_sync)

    async def export_rows(self) -> list[dict[str, Any]]:
        return [record.model_dump(mode="json") for record in self._records]
