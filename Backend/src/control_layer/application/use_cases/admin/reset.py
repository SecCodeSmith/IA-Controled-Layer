from __future__ import annotations

from typing import Protocol

from control_layer.domain.models.enums import ApprovalStatus
from control_layer.domain.models.risk import RiskProfile
from control_layer.domain.ports.approval_repository import ApprovalRepository
from control_layer.domain.ports.audit_repository import AuditRepository
from control_layer.domain.ports.budget_repository import BudgetRepository
from control_layer.domain.ports.cache_repository import CacheRepository
from control_layer.domain.ports.risk_repository import RiskRepository
from control_layer.domain.ports.session_repository import SessionRepository

_CACHE_PREFIXES: tuple[str, ...] = (
    "decision:",
    "rate:",
    "loop:",
    "cb:",
    "quarantine:",
    "seen:",
    "calls:",
)


class _ResettableMetrics(Protocol):
    def reset(self) -> None: ...


class ResetDemoUseCase:
    def __init__(
        self,
        audit_repository: AuditRepository,
        alert_store: object,
        budget_repository: BudgetRepository,
        session_repository: SessionRepository,
        risk_repository: RiskRepository,
        approval_repository: ApprovalRepository,
        cache: CacheRepository,
        metrics_collector: _ResettableMetrics,
    ) -> None:
        self._audit_repository = audit_repository
        self._alert_store = alert_store
        self._budget_repository = budget_repository
        self._session_repository = session_repository
        self._risk_repository = risk_repository
        self._approval_repository = approval_repository
        self._cache = cache
        self._metrics_collector = metrics_collector

    async def execute(self) -> None:
        await self._audit_repository.clear()
        await self._clear_alerts()
        await self._budget_repository.reset()
        await self._session_repository.clear()
        await self._clear_risk_profiles()
        await self._clear_pending_approvals()
        self._metrics_collector.reset()
        for prefix in _CACHE_PREFIXES:
            await self._cache.flush(prefix)

    async def _clear_alerts(self) -> None:
        # AlertStore has no clear() in its domain port yet; call it only if the concrete
        # adapter happens to provide one, so the reset degrades gracefully otherwise.
        clear = getattr(self._alert_store, "clear", None)
        if clear is not None:
            await clear()

    async def _clear_risk_profiles(self) -> None:
        for profile in await self._risk_repository.list_all():
            await self._risk_repository.update(RiskProfile(sub=profile.sub))

    async def _clear_pending_approvals(self) -> None:
        for approval in await self._approval_repository.list_pending():
            await self._approval_repository.update_status(approval.id, ApprovalStatus.expired)
