from __future__ import annotations

from datetime import UTC, datetime

from control_layer.application.audit.call_record_builder import CallRecordBuilder
from control_layer.domain.models.audit import TokensInfo
from control_layer.domain.models.enums import CallKind, CallStatus, Role, StageName
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.provider import ProviderInfo


def _identity() -> Identity:
    return Identity(
        sub="anna.kowalska",
        name="Anna Kowalska",
        role=Role.developer,
        location="Krakow, PL",
        region="PL",
        agent_id="agent-anna-dev-7f3a",
    )


def test_build_assembles_full_call_record() -> None:
    builder = CallRecordBuilder()
    record = builder.build(
        call_id="c_000139",
        identity=_identity(),
        kind=CallKind.tool_call,
        target="logs-db.query",
        mcp_server="logs-db",
        status=CallStatus.MASKED,
        stage=StageName.dlp,
        rule_id="pii_masking",
        reason="3 email addresses masked",
        owasp=["LLM02"],
        matched_rule_yaml="- id: pii_masking\n",
        request_summary="tool: logs-db.query",
        request_payload={"service": "auth"},
        raw_response="raw",
        delivered_response="delivered",
        items_masked=3,
        tokens=TokensInfo(prompt=0, completion=0, total=0),
        cost_usd=0.0,
        proxy_latency_ms=4.2,
        upstream_latency_ms=31.0,
        stage_timings={"dlp": 1.1},
        provider=ProviderInfo(name="ollama", model="qwen2.5:7b"),
        timestamp=datetime(2026, 10, 3, 10, 41, 40, tzinfo=UTC),
    )
    assert record.call_id == "c_000139"
    assert record.decision.status == CallStatus.MASKED
    assert record.decision.rule_id == "pii_masking"
    assert record.response.raw == "raw"
    assert record.response.delivered == "delivered"
    assert record.items_masked == 3
    assert record.latency.proxy_ms == 4.2
    assert record.provider.name == "ollama"


def test_build_applies_sensible_defaults() -> None:
    builder = CallRecordBuilder()
    record = builder.build(
        call_id="c_1",
        identity=_identity(),
        kind=CallKind.chat,
        target="llm.complete",
        status=CallStatus.ALLOWED,
        provider=ProviderInfo(name="mock", model="mock"),
    )
    assert record.mcp_server is None
    assert record.decision.stage is None
    assert record.decision.rule_id is None
    assert record.items_masked == 0
    assert record.tokens.total == 0
    assert record.request.payload == {}
