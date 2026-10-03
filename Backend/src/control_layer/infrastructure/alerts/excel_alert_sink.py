from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import openpyxl

from control_layer.infrastructure._util import get_field

_FIELDS = (
    "id",
    "created_at",
    "call_id",
    "user",
    "status",
    "stage",
    "rule_id",
    "severity",
    "owasp",
    "reason",
    "evidence",
)


_PRIMITIVE_TYPES = (str, int, float, bool, datetime, date, type(None))


def _cell_value(value: Any) -> Any:
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    if isinstance(value, _PRIMITIVE_TYPES):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        value = model_dump(mode="json")
    if isinstance(value, _PRIMITIVE_TYPES):
        return value
    return json.dumps(value, default=str)


class ExcelAlertSink:
    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._lock = asyncio.Lock()

    def _write_row_sync(self, alert: Any) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._path.exists():
            workbook = openpyxl.load_workbook(self._path)
            worksheet = workbook.active
        else:
            workbook = openpyxl.Workbook()
            worksheet = workbook.active
            worksheet.append(list(_FIELDS))

        row = [_cell_value(get_field(alert, field)) for field in _FIELDS]
        worksheet.append(row)
        workbook.save(self._path)

    async def emit(self, alert: Any) -> None:
        async with self._lock:
            await asyncio.to_thread(self._write_row_sync, alert)
