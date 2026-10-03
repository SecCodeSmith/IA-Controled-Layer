from __future__ import annotations

from datetime import UTC, datetime

from control_layer.application.use_cases.admin.audit import (
    CallNotFoundError,
    GetCallDetailUseCase,
    ListAuditUseCase,
)
from control_layer.application.use_cases.admin.feed import FeedQuery, ListFeedUseCase
from control_layer.domain.models.audit import (
    CallDecisionInfo,
    CallLatency,
    CallRecord,
    CallRequestInfo,
    CallResponseInfo,
    TokensInfo,
)
from control_layer.domain.models.enums import CallKind, CallStatus, Role
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.provider import ProviderInfo

import pytest


def _record(call_id: str) -> CallRecord:
    return CallRecord(
        call_id=call_id,
        timestamp=datetime.now(UTC),
        identity=Identity(
            sub="anna.kowalska",
            name="Anna Kowalska",
            role=Role.developer,
            location="Krakow, PL",
            region="PL",
            agent_id="agent-anna-dev-7f3a",
        ),
        kind=CallKind.chat,
        target="llm.complete",
        decision=CallDecisionInfo(status=CallStatus.ALLOWED),
        request=CallRequestInfo(summary="prompt"),
        response=CallResponseInfo(raw="hi", delivered="hi"),
        tokens=TokensInfo(prompt=1, completion=1, total=2),
        latency=CallLatency(proxy_ms=1.0, upstream_ms=1.0, stages={}),
        provider=ProviderInfo(name="mock", model="mock"),
    )


class FakeAuditRepository:
    def __init__(self, records: list[CallRecord]) -> None:
        self._records = records

    async def append(self, record: CallRecord) -> None:
        self._records.append(record)

    async def list_recent(self, limit: int = 100) -> list[CallRecord]:
        return self._records[-limit:]

    async def get(self, call_id: str) -> CallRecord | None:
        return next((r for r in self._records if r.call_id == call_id), None)

    async def clear(self) -> None:
        self._records.clear()

    async def export_rows(self) -> list[dict]:
        return [r.model_dump(mode="json") for r in self._records]


async def test_list_feed_use_case_returns_recent_records() -> None:
    repo = FakeAuditRepository([_record("c_1"), _record("c_2")])
    use_case = ListFeedUseCase(repo)

    result = await use_case.execute(FeedQuery(limit=10))

    assert [r.call_id for r in result] == ["c_1", "c_2"]


async def test_list_audit_use_case_returns_records() -> None:
    repo = FakeAuditRepository([_record("c_1")])
    use_case = ListAuditUseCase(repo)

    result = await use_case.execute(FeedQuery(limit=10))

    assert [r.call_id for r in result] == ["c_1"]


async def test_get_call_detail_returns_matching_record() -> None:
    repo = FakeAuditRepository([_record("c_1"), _record("c_2")])
    use_case = GetCallDetailUseCase(repo)

    result = await use_case.execute("c_2")

    assert result.call_id == "c_2"


async def test_get_call_detail_raises_when_missing() -> None:
    repo = FakeAuditRepository([])
    use_case = GetCallDetailUseCase(repo)

    with pytest.raises(CallNotFoundError):
        await use_case.execute("missing")
