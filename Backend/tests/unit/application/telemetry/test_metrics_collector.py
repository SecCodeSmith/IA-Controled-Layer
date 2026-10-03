from __future__ import annotations

from datetime import UTC, datetime

from control_layer.application.telemetry.metrics_collector import MetricsCollector
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


def _identity(sub: str = "anna.kowalska") -> Identity:
    return Identity(
        sub=sub,
        name="Anna Kowalska",
        role=Role.developer,
        location="Krakow, PL",
        region="PL",
        agent_id="agent-anna-dev-7f3a",
    )


def _call_record(
    *,
    proxy_ms: float,
    upstream_ms: float,
    stages: dict[str, float],
) -> CallRecord:
    return CallRecord(
        call_id="c_000001",
        timestamp=datetime.now(UTC),
        identity=_identity(),
        kind=CallKind.chat,
        target="llm.complete",
        decision=CallDecisionInfo(status=CallStatus.ALLOWED),
        request=CallRequestInfo(summary="prompt"),
        response=CallResponseInfo(raw="hi", delivered="hi"),
        tokens=TokensInfo(prompt=1, completion=1, total=2),
        latency=CallLatency(proxy_ms=proxy_ms, upstream_ms=upstream_ms, stages=stages),
        provider=ProviderInfo(name="mock", model="mock"),
    )


def test_record_accumulates_stage_proxy_and_upstream_samples() -> None:
    collector = MetricsCollector()
    for value in (1.0, 2.0, 3.0, 4.0, 5.0):
        collector.record(
            _call_record(proxy_ms=value, upstream_ms=value * 100, stages={"dlp": value})
        )

    snapshot = collector.snapshot()

    assert snapshot.stages["dlp"].count == 5
    assert snapshot.stages["dlp"].p50_ms == 3.0
    assert snapshot.proxy.p50_ms == 3.0
    assert snapshot.upstream.p50_ms == 300.0


def test_percentiles_use_linear_interpolation() -> None:
    collector = MetricsCollector()
    for value in (1.0, 2.0, 3.0, 4.0, 5.0):
        collector.record(_call_record(proxy_ms=value, upstream_ms=0.0, stages={}))

    snapshot = collector.snapshot()

    assert snapshot.proxy.p50_ms == 3.0
    assert snapshot.proxy.p95_ms == 4.8


def test_stage_samples_bounded_to_last_5000() -> None:
    collector = MetricsCollector()
    for i in range(5010):
        collector.record(_call_record(proxy_ms=0.0, upstream_ms=0.0, stages={"dlp": float(i)}))

    snapshot = collector.snapshot()

    assert snapshot.stages["dlp"].count == 5000


def test_record_cache_hit_and_miss_ratio() -> None:
    collector = MetricsCollector()
    collector.record_cache(True)
    collector.record_cache(True)
    collector.record_cache(False)

    snapshot = collector.snapshot()

    assert snapshot.cache.hits == 2
    assert snapshot.cache.misses == 1
    assert snapshot.cache.hit_ratio == 2 / 3


def test_cache_hit_ratio_is_zero_when_no_samples() -> None:
    collector = MetricsCollector()

    snapshot = collector.snapshot()

    assert snapshot.cache.hit_ratio == 0.0


def test_calls_per_minute_uses_sixty_second_window() -> None:
    now = [1000.0]
    collector = MetricsCollector(clock=lambda: now[0])

    collector.record(_call_record(proxy_ms=1.0, upstream_ms=1.0, stages={}))
    now[0] = 1030.0
    collector.record(_call_record(proxy_ms=1.0, upstream_ms=1.0, stages={}))
    now[0] = 1090.0
    collector.record(_call_record(proxy_ms=1.0, upstream_ms=1.0, stages={}))

    snapshot = collector.snapshot()

    assert snapshot.calls_per_minute == 2.0


def test_reset_clears_every_sample_and_counter() -> None:
    collector = MetricsCollector()
    collector.record(_call_record(proxy_ms=1.0, upstream_ms=1.0, stages={"dlp": 1.0}))
    collector.record_cache(True)

    collector.reset()
    snapshot = collector.snapshot()

    assert snapshot.stages == {}
    assert snapshot.proxy.p50_ms == 0.0
    assert snapshot.cache.hits == 0
    assert snapshot.cache.misses == 0
    assert snapshot.cache.hit_ratio == 0.0
    assert snapshot.calls_per_minute == 0.0


def test_prometheus_text_renders_expected_metric_lines() -> None:
    collector = MetricsCollector()
    collector.record(_call_record(proxy_ms=4.0, upstream_ms=800.0, stages={"dlp": 2.0}))
    collector.record_cache(True)
    collector.record_cache(False)
    collector.record_cache(False)

    text = collector.prometheus_text()

    assert "control_layer_calls_total 1" in text
    assert 'control_layer_stage_latency_ms{stage="dlp",quantile="0.5"} 2.0' in text
    assert 'control_layer_stage_latency_ms{stage="dlp",quantile="0.95"} 2.0' in text
    assert "control_layer_cache_hit_ratio" in text
    cache_line = next(
        line for line in text.splitlines() if line.startswith("control_layer_cache_hit_ratio ")
    )
    assert float(cache_line.split()[-1]) == 1 / 3


def test_prometheus_text_total_counter_is_not_bounded_by_sample_window() -> None:
    collector = MetricsCollector()
    for _ in range(3):
        collector.record(_call_record(proxy_ms=1.0, upstream_ms=1.0, stages={}))

    text = collector.prometheus_text()

    assert "control_layer_calls_total 3" in text


def test_record_accumulates_added_delay_samples() -> None:
    collector = MetricsCollector()
    for value in (1.0, 2.0, 3.0, 4.0, 5.0):
        collector.record(_call_record(proxy_ms=value + 100.0, upstream_ms=100.0, stages={}))

    snapshot = collector.snapshot()

    assert snapshot.overhead.p50_ms == 3.0
    assert snapshot.overhead.p95_ms == 4.8


def test_prometheus_text_exposes_added_delay() -> None:
    collector = MetricsCollector()
    collector.record(_call_record(proxy_ms=7.0, upstream_ms=5.0, stages={}))

    text = collector.prometheus_text()

    assert 'control_layer_overhead_ms{quantile="0.5"} 2.0' in text
