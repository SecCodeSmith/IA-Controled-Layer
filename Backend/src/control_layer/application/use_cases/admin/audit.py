from __future__ import annotations

from control_layer.application.use_cases.admin._shared import load_all_call_records
from control_layer.application.use_cases.admin.feed import FeedQuery, apply_feed_filters
from control_layer.domain.exceptions import ControlLayerError
from control_layer.domain.models.audit import CallRecord
from control_layer.domain.ports.audit_repository import AuditRepository


class CallNotFoundError(ControlLayerError):
    def __init__(self, call_id: str) -> None:
        super().__init__(f"call not found: {call_id}")
        self.call_id = call_id


class ListAuditUseCase:
    def __init__(self, audit_repository: AuditRepository) -> None:
        self._audit_repository = audit_repository

    async def execute(self, query: FeedQuery) -> list[CallRecord]:
        records = await load_all_call_records(self._audit_repository)
        return apply_feed_filters(records, query)


class GetCallDetailUseCase:
    def __init__(self, audit_repository: AuditRepository) -> None:
        self._audit_repository = audit_repository

    async def execute(self, call_id: str) -> CallRecord:
        record = await self._audit_repository.get(call_id)
        if record is None:
            raise CallNotFoundError(call_id)
        return record
