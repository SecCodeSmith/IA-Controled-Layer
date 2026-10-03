from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from control_layer.infrastructure._util import get_field, to_mapping


class JsonlAuditRepository:
    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._records: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._load_existing()

    def _load_existing(self) -> None:
        if not self._path.exists():
            return
        with self._path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    self._records.append(json.loads(line))

    def _append_line_sync(self, mapping: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(mapping, default=str) + "\n")

    def _truncate_sync(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text("", encoding="utf-8")

    async def append(self, record: Any) -> None:
        mapping = dict(to_mapping(record))
        async with self._lock:
            self._records.append(mapping)
            await asyncio.to_thread(self._append_line_sync, mapping)

    @staticmethod
    def _matches(record: Any, key: str, value: Any) -> bool:
        if key == "user":
            candidate = get_field(record, "user")
            if candidate is None:
                candidate = get_field(record, "identity")
            sub = get_field(candidate, "sub") if candidate is not None else None
            return sub == value
        return get_field(record, key) == value

    async def list_recent(self, limit: int, **filters: Any) -> list[dict[str, Any]]:
        items = list(reversed(self._records))
        for key, value in filters.items():
            if value is None:
                continue
            items = [record for record in items if self._matches(record, key, value)]
        return items[:limit]

    async def get(self, call_id: str) -> dict[str, Any] | None:
        for record in reversed(self._records):
            if get_field(record, "call_id") == call_id:
                return record
        return None

    async def clear(self) -> None:
        async with self._lock:
            self._records.clear()
            await asyncio.to_thread(self._truncate_sync)

    async def export_rows(self) -> list[dict[str, Any]]:
        return list(self._records)
