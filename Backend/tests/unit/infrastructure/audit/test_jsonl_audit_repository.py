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


def _record(**overrides) -> dict:
    base = {
        "call_id": "c_1",
        "timestamp": "2026-10-03T10:41:40Z",
        "identity": {"sub": "anna.kowalska", "name": "Anna Kowalska", "role": "developer"},
        "kind": "tool_call",
        "target": "logs-db.query",
        "status": "MASKED",
        "stage": "dlp",
        "rule_id": "pii_masking",
    }
    base.update(overrides)
    return base


async def test_append_then_get(tmp_path: Path) -> None:
    repo = JsonlAuditRepository(tmp_path / "calls.jsonl")

    await repo.append(_record(call_id="c_1"))

    record = await repo.get("c_1")
    assert record is not None
    assert record["call_id"] == "c_1"


async def test_get_missing_returns_none(tmp_path: Path) -> None:
    repo = JsonlAuditRepository(tmp_path / "calls.jsonl")

    assert await repo.get("missing") is None


async def test_list_recent_returns_newest_first(tmp_path: Path) -> None:
    repo = JsonlAuditRepository(tmp_path / "calls.jsonl")
    await repo.append(_record(call_id="c_1"))
    await repo.append(_record(call_id="c_2"))

    items = await repo.list_recent(limit=10)

    assert [item["call_id"] for item in items] == ["c_2", "c_1"]


async def test_list_recent_filters_by_status(tmp_path: Path) -> None:
    repo = JsonlAuditRepository(tmp_path / "calls.jsonl")
    await repo.append(_record(call_id="c_1", status="ALLOWED"))
    await repo.append(_record(call_id="c_2", status="BLOCKED"))

    items = await repo.list_recent(limit=10, status="BLOCKED")

    assert [item["call_id"] for item in items] == ["c_2"]


async def test_list_recent_filters_by_user_sub(tmp_path: Path) -> None:
    repo = JsonlAuditRepository(tmp_path / "calls.jsonl")
    await repo.append(
        _record(call_id="c_1", identity={"sub": "anna.kowalska", "name": "A", "role": "developer"})
    )
    await repo.append(
        _record(call_id="c_2", identity={"sub": "marek.nowak", "name": "M", "role": "hr"})
    )

    items = await repo.list_recent(limit=10, user="marek.nowak")

    assert [item["call_id"] for item in items] == ["c_2"]


async def test_clear_empties_store_and_file(tmp_path: Path) -> None:
    path = tmp_path / "calls.jsonl"
    repo = JsonlAuditRepository(path)
    await repo.append(_record(call_id="c_1"))

    await repo.clear()

    assert await repo.list_recent(limit=10) == []
    assert path.read_text(encoding="utf-8").strip() == ""


async def test_export_rows_returns_all_records_in_append_order(tmp_path: Path) -> None:
    repo = JsonlAuditRepository(tmp_path / "calls.jsonl")
    await repo.append(_record(call_id="c_1"))
    await repo.append(_record(call_id="c_2"))

    rows = await repo.export_rows()

    assert [row["call_id"] for row in rows] == ["c_1", "c_2"]


async def test_jsonl_file_is_append_only_and_durable(tmp_path: Path) -> None:
    path = tmp_path / "calls.jsonl"
    repo1 = JsonlAuditRepository(path)
    await repo1.append(_record(call_id="c_1"))
    await repo1.append(_record(call_id="c_2"))

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["call_id"] == "c_1"


async def test_durability_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "calls.jsonl"
    repo1 = JsonlAuditRepository(path)
    await repo1.append(_record(call_id="c_1"))
    await repo1.append(_record(call_id="c_2"))

    repo2 = JsonlAuditRepository(path)
    record = await repo2.get("c_1")
    items = await repo2.list_recent(limit=10)

    assert record is not None
    assert [item["call_id"] for item in items] == ["c_2", "c_1"]


def _real_call_record(**overrides: object) -> CallRecord:
    base: dict[str, object] = {
        "call_id": "c_real",
        "timestamp": datetime(2026, 10, 3, 10, 41, 40, tzinfo=UTC),
        "identity": Identity(
            sub="anna.kowalska",
            name="Anna Kowalska",
            role="developer",
            location="Krakow, PL",
            region="PL",
            agent_id="agent-anna-dev-7f3a",
        ),
        "kind": "tool_call",
        "target": "logs-db.query",
        "decision": CallDecisionInfo(status="MASKED", stage="dlp", rule_id="pii_masking"),
        "request": CallRequestInfo(summary="tool: logs-db.query"),
        "response": CallResponseInfo(raw="raw", delivered="masked"),
        "tokens": TokensInfo(),
        "latency": CallLatency(proxy_ms=1.0, upstream_ms=2.0),
        "provider": ProviderInfo(name="mock", model="mock"),
    }
    base.update(overrides)
    return CallRecord(**base)


async def test_accepts_real_domain_call_record(tmp_path: Path) -> None:
    repo = JsonlAuditRepository(tmp_path / "calls.jsonl")

    await repo.append(_real_call_record())

    record = await repo.get("c_real")
    assert record is not None
    assert record["identity"]["sub"] == "anna.kowalska"
    assert record["decision"]["rule_id"] == "pii_masking"

    items = await repo.list_recent(limit=10, user="anna.kowalska")
    assert [item["call_id"] for item in items] == ["c_real"]
