from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path

import openpyxl

from control_layer.domain.exceptions import ControlLayerError
from control_layer.domain.models.audit import CallRecord
from control_layer.domain.ports.audit_repository import AuditRepository

_JSONL_MEDIA_TYPE = "application/jsonl"
_CSV_MEDIA_TYPE = "text/csv"
_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_CSV_HEADER = list(CallRecord.model_fields.keys())


@dataclass(frozen=True)
class ExportFile:
    filename: str
    media_type: str
    content: bytes


class ExportNotAvailableError(ControlLayerError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _stringify(value: object) -> object:
    if isinstance(value, dict | list):
        return json.dumps(value, default=str)
    return value


def _build_jsonl(rows: list[dict]) -> bytes:
    if not rows:
        return b""
    lines = (json.dumps(row, default=str) for row in rows)
    return ("\n".join(lines) + "\n").encode("utf-8")


def _build_csv(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    if rows:
        writer = csv.DictWriter(
            buffer, fieldnames=_CSV_HEADER, extrasaction="ignore", restval=""
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _stringify(value) for key, value in row.items()})
    return buffer.getvalue().encode("utf-8")


def _build_xlsx(rows: list[dict]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(_CSV_HEADER)
    for row in rows:
        sheet.append([_stringify(row.get(column)) for column in _CSV_HEADER])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


class ExportAuditUseCase:
    def __init__(self, audit_repository: AuditRepository) -> None:
        self._audit_repository = audit_repository

    async def execute(self, fmt: str) -> ExportFile:
        rows = await self._audit_repository.export_rows()
        if fmt == "jsonl":
            return ExportFile("audit.jsonl", _JSONL_MEDIA_TYPE, _build_jsonl(rows))
        if fmt == "csv":
            return ExportFile("audit.csv", _CSV_MEDIA_TYPE, _build_csv(rows))
        if fmt == "xlsx":
            return ExportFile("audit.xlsx", _XLSX_MEDIA_TYPE, _build_xlsx(rows))
        raise ValueError(f"unsupported export format: {fmt!r}")


class ExportAlertsUseCase:
    def __init__(self, alerts_xlsx_path: Path | str) -> None:
        self._path = Path(alerts_xlsx_path)

    async def execute(self) -> ExportFile:
        if not self._path.exists():
            raise ExportNotAvailableError(f"alerts export not available at {self._path}")
        content = self._path.read_bytes()
        return ExportFile(self._path.name, _XLSX_MEDIA_TYPE, content)
