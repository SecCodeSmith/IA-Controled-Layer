from __future__ import annotations

from datetime import UTC, datetime

from control_layer.domain.models.audit import (
    CallDecisionInfo,
    CallLatency,
    CallRecord,
    CallRequestInfo,
    CallResponseInfo,
    TokensInfo,
)
from control_layer.domain.models.enums import CallKind, CallStatus, StageName
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.provider import ProviderInfo


class CallRecordBuilder:
    def build(
        self,
        *,
        call_id: str,
        identity: Identity,
        kind: CallKind,
        target: str,
        status: CallStatus,
        provider: ProviderInfo,
        mcp_server: str | None = None,
        stage: StageName | None = None,
        rule_id: str | None = None,
        reason: str | None = None,
        owasp: list[str] | None = None,
        matched_rule_yaml: str | None = None,
        request_summary: str = "",
        request_payload: dict | None = None,
        raw_response: str | None = None,
        delivered_response: str | None = None,
        items_masked: int = 0,
        tokens: TokensInfo | None = None,
        cost_usd: float = 0.0,
        proxy_latency_ms: float = 0.0,
        upstream_latency_ms: float = 0.0,
        stage_timings: dict[str, float] | None = None,
        timestamp: datetime | None = None,
    ) -> CallRecord:
        return CallRecord(
            call_id=call_id,
            timestamp=timestamp or datetime.now(UTC),
            identity=identity,
            kind=kind,
            target=target,
            mcp_server=mcp_server,
            decision=CallDecisionInfo(
                status=status, stage=stage, rule_id=rule_id, reason=reason, owasp=owasp or []
            ),
            matched_rule_yaml=matched_rule_yaml,
            request=CallRequestInfo(summary=request_summary, payload=request_payload or {}),
            response=CallResponseInfo(raw=raw_response, delivered=delivered_response),
            items_masked=items_masked,
            tokens=tokens or TokensInfo(),
            cost_usd=cost_usd,
            latency=CallLatency(
                proxy_ms=proxy_latency_ms,
                upstream_ms=upstream_latency_ms,
                stages=stage_timings or {},
            ),
            provider=provider,
        )
