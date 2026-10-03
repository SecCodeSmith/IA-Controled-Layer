from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from control_layer.domain.models.audit import (
    CallDecisionInfo,
    CallLatency,
    CallRecord,
    CallRequestInfo,
    CallResponseInfo,
    TokensInfo,
)
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.provider import ProviderInfo
from control_layer.infrastructure.audit.jsonl_audit_repository import JsonlAuditRepository


def _record(
    call_id: str = "c_1",
    status: str = "MASKED",
    sub: str = "anna.kowalska",
    raw: str = "raw",
) -> CallRecord:
    return CallRecord(
        call_id=call_id,
        timestamp=datetime(2026, 10, 3, 10, 41, 40, tzinfo=UTC),
        identity=Identity(
            sub=sub,
            name=sub,
            role="developer",
            location="Krakow, PL",
            region="PL",
            agent_id="agent-1",
        ),
        kind="tool_call",
        target="logs-db.query",
        decision=CallDecisionInfo(status=status, stage="dlp", rule_id="pii_masking"),
        request=CallRequestInfo(summary="tool: logs-db.query"),
        response=CallResponseInfo(raw=raw, delivered="masked"),
        tokens=TokensInfo(),
        latency=CallLatency(proxy_ms=1.0, upstream_ms=2.0),
        provider=ProviderInfo(name="mock", model="mock"),
    )


async def test_append_then_get(tmp_path: Path) -> None:
    repo = JsonlAuditRepository(tmp_path / "calls.jsonl")

    await repo.append(_record("c_1"))

    record = await repo.get("c_1")
    assert isinstance(record, CallRecord)
    assert record.call_id == "c_1"


async def test_get_missing_returns_none(tmp_path: Path) -> None:
    repo = JsonlAuditRepository(tmp_path / "calls.jsonl")

    assert await repo.get("missing") is None


async def test_list_recent_returns_newest_first(tmp_path: Path) -> None:
    repo = JsonlAuditRepository(tmp_path / "calls.jsonl")
    await repo.append(_record("c_1"))
    await repo.append(_record("c_2"))

    items = await repo.list_recent(limit=10)

    assert [item.call_id for item in items] == ["c_2", "c_1"]


async def test_list_recent_filters_by_status(tmp_path: Path) -> None:
    repo = JsonlAuditRepository(tmp_path / "calls.jsonl")
    await repo.append(_record("c_1", status="ALLOWED"))
    await repo.append(_record("c_2", status="BLOCKED"))

    items = await repo.list_recent(limit=10, status="BLOCKED")

    assert [item.call_id for item in items] == ["c_2"]


async def test_list_recent_filters_by_user_sub(tmp_path: Path) -> None:
    repo = JsonlAuditRepository(tmp_path / "calls.jsonl")
    await repo.append(_record("c_1", sub="anna.kowalska"))
    await repo.append(_record("c_2", sub="marek.nowak"))

    items = await repo.list_recent(limit=10, user="marek.nowak")

    assert [item.call_id for item in items] == ["c_2"]


async def test_clear_empties_store_and_file(tmp_path: Path) -> None:
    path = tmp_path / "calls.jsonl"
    repo = JsonlAuditRepository(path)
    await repo.append(_record("c_1"))

    await repo.clear()

    assert await repo.list_recent(limit=10) == []
    assert path.read_text(encoding="utf-8").strip() == ""


async def test_export_rows_returns_json_dicts_in_append_order(tmp_path: Path) -> None:
    repo = JsonlAuditRepository(tmp_path / "calls.jsonl")
    await repo.append(_record("c_1"))
    await repo.append(_record("c_2"))

    rows = await repo.export_rows()

    assert [row["call_id"] for row in rows] == ["c_1", "c_2"]
    assert isinstance(rows[0], dict)
    assert rows[0]["identity"]["sub"] == "anna.kowalska"
    json.dumps(rows)


async def test_jsonl_file_is_append_only(tmp_path: Path) -> None:
    path = tmp_path / "calls.jsonl"
    repo = JsonlAuditRepository(path)
    await repo.append(_record("c_1"))
    await repo.append(_record("c_2"))

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["call_id"] == "c_1"


async def test_reload_from_file_returns_call_records(tmp_path: Path) -> None:
    path = tmp_path / "calls.jsonl"
    repo1 = JsonlAuditRepository(path)
    await repo1.append(_record("c_1"))
    await repo1.append(_record("c_2"))

    repo2 = JsonlAuditRepository(path)
    record = await repo2.get("c_1")
    items = await repo2.list_recent(limit=10)

    assert isinstance(record, CallRecord)
    assert record.identity.sub == "anna.kowalska"
    assert all(isinstance(item, CallRecord) for item in items)
    assert [item.call_id for item in items] == ["c_2", "c_1"]


async def test_get_returns_latest_for_duplicate_call_ids(tmp_path: Path) -> None:
    path = tmp_path / "calls.jsonl"
    repo1 = JsonlAuditRepository(path)
    await repo1.append(_record("c_1", raw="old"))
    repo2 = JsonlAuditRepository(path)
    await repo2.append(_record("c_1", raw="new"))

    repo3 = JsonlAuditRepository(path)
    record = await repo3.get("c_1")

    assert record is not None
    assert record.response.raw == "new"


async def test_invalid_lines_are_skipped_on_load(tmp_path: Path) -> None:
    path = tmp_path / "calls.jsonl"
    repo1 = JsonlAuditRepository(path)
    await repo1.append(_record("c_1"))
    with path.open("a", encoding="utf-8") as fh:
        fh.write('{"call_id": "broken"}\n')

    repo2 = JsonlAuditRepository(path)

    assert [r.call_id for r in await repo2.list_recent(limit=10)] == ["c_1"]


async def test_clear_truncates_the_file_and_a_restart_loads_nothing(tmp_path: Path) -> None:
    path = tmp_path / "calls.jsonl"
    repo = JsonlAuditRepository(path)
    await repo.append(_record("c_1"))

    await repo.clear()

    assert path.stat().st_size == 0
    assert await JsonlAuditRepository(path).export_rows() == []
    await repo.append(_record("c_2"))
    assert [r["call_id"] for r in await JsonlAuditRepository(path).export_rows()] == ["c_2"]
