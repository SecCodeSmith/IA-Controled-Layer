from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from control_layer.application.use_cases.admin._shared import load_all_call_records
from control_layer.domain.models.audit import CallRecord
from control_layer.domain.ports.audit_repository import AuditRepository


class FeedQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    user: str | None = None
    role: str | None = None
    status: str | None = None
    kind: str | None = None
    limit: int = 100


def apply_feed_filters(records: list[CallRecord], query: FeedQuery) -> list[CallRecord]:
    filtered = records
    if query.user is not None:
        filtered = [r for r in filtered if r.identity.sub == query.user]
    if query.role is not None:
        filtered = [r for r in filtered if r.identity.role.value == query.role]
    if query.status is not None:
        filtered = [r for r in filtered if r.decision.status.value == query.status]
    if query.kind is not None:
        filtered = [r for r in filtered if r.kind.value == query.kind]
    if query.limit:
        filtered = filtered[-query.limit :]
    return filtered


class ListFeedUseCase:
    def __init__(self, audit_repository: AuditRepository) -> None:
        self._audit_repository = audit_repository

    async def execute(self, query: FeedQuery) -> list[CallRecord]:
        records = await load_all_call_records(self._audit_repository)
        return apply_feed_filters(records, query)
