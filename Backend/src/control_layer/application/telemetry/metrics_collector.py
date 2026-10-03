from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable
from math import ceil, floor

from pydantic import BaseModel, ConfigDict, Field

from control_layer.domain.models.audit import CallRecord

_MAX_SAMPLES = 5000
_CALLS_PER_MINUTE_WINDOW_S = 60.0


class StageMetric(BaseModel):
    model_config = ConfigDict(frozen=True)

    p50_ms: float
    p95_ms: float
    count: int


class LatencyBand(BaseModel):
    model_config = ConfigDict(frozen=True)

    p50_ms: float
    p95_ms: float


class CacheMetric(BaseModel):
    model_config = ConfigDict(frozen=True)

    hits: int
    misses: int
    hit_ratio: float


class MetricsView(BaseModel):
    model_config = ConfigDict(frozen=True)

    stages: dict[str, StageMetric] = Field(default_factory=dict)
    proxy: LatencyBand
    upstream: LatencyBand
    overhead: LatencyBand
    cache: CacheMetric
    calls_per_minute: float


def _percentile(sorted_samples: list[float], pct: float) -> float:
    if not sorted_samples:
        return 0.0
    if len(sorted_samples) == 1:
        return sorted_samples[0]
    rank = (len(sorted_samples) - 1) * pct
    lower = floor(rank)
    upper = ceil(rank)
    if lower == upper:
        return sorted_samples[int(rank)]
    lower_value = sorted_samples[lower] * (upper - rank)
    upper_value = sorted_samples[upper] * (rank - lower)
    return lower_value + upper_value


def _band(samples: deque[float]) -> LatencyBand:
    ordered = sorted(samples)
    return LatencyBand(p50_ms=_percentile(ordered, 0.5), p95_ms=_percentile(ordered, 0.95))


class MetricsCollector:
    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._stage_samples: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=_MAX_SAMPLES)
        )
        self._proxy_samples: deque[float] = deque(maxlen=_MAX_SAMPLES)
        self._upstream_samples: deque[float] = deque(maxlen=_MAX_SAMPLES)
        self._overhead_samples: deque[float] = deque(maxlen=_MAX_SAMPLES)
        self._call_timestamps: deque[float] = deque(maxlen=_MAX_SAMPLES)
        self._cache_hits = 0
        self._cache_misses = 0
        self._total_calls = 0

    def record(self, call_record: CallRecord) -> None:
        for stage_name, timing_ms in call_record.latency.stages.items():
            self._stage_samples[stage_name].append(timing_ms)
        self._proxy_samples.append(call_record.latency.proxy_ms)
        self._upstream_samples.append(call_record.latency.upstream_ms)
        self._overhead_samples.append(call_record.latency.overhead_ms)
        self._call_timestamps.append(self._clock())
        self._total_calls += 1

    def record_cache(self, hit: bool) -> None:
        if hit:
            self._cache_hits += 1
        else:
            self._cache_misses += 1

    def snapshot(self) -> MetricsView:
        window_start = self._clock() - _CALLS_PER_MINUTE_WINDOW_S
        calls_per_minute = float(sum(1 for t in self._call_timestamps if t >= window_start))
        stages = {
            name: StageMetric(
                p50_ms=_percentile(sorted(samples), 0.5),
                p95_ms=_percentile(sorted(samples), 0.95),
                count=len(samples),
            )
            for name, samples in self._stage_samples.items()
        }
        total_cache = self._cache_hits + self._cache_misses
        hit_ratio = (self._cache_hits / total_cache) if total_cache else 0.0
        return MetricsView(
            stages=stages,
            proxy=_band(self._proxy_samples),
            upstream=_band(self._upstream_samples),
            overhead=_band(self._overhead_samples),
            cache=CacheMetric(
                hits=self._cache_hits, misses=self._cache_misses, hit_ratio=hit_ratio
            ),
            calls_per_minute=calls_per_minute,
        )

    def reset(self) -> None:
        self._stage_samples.clear()
        self._proxy_samples.clear()
        self._upstream_samples.clear()
        self._overhead_samples.clear()
        self._call_timestamps.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        self._total_calls = 0

    def prometheus_text(self) -> str:
        snapshot = self.snapshot()
        lines = [
            "# HELP control_layer_calls_total Total calls processed by the control layer.",
            "# TYPE control_layer_calls_total counter",
            f"control_layer_calls_total {self._total_calls}",
            "# HELP control_layer_stage_latency_ms Per-stage latency percentiles in milliseconds.",
            "# TYPE control_layer_stage_latency_ms gauge",
        ]
        for stage_name in sorted(snapshot.stages):
            metric = snapshot.stages[stage_name]
            lines.append(
                f'control_layer_stage_latency_ms{{stage="{stage_name}",quantile="0.5"}} '
                f"{metric.p50_ms}"
            )
            lines.append(
                f'control_layer_stage_latency_ms{{stage="{stage_name}",quantile="0.95"}} '
                f"{metric.p95_ms}"
            )
        lines += [
            "# HELP control_layer_proxy_latency_ms Proxy overhead latency percentiles "
            "in milliseconds.",
            "# TYPE control_layer_proxy_latency_ms gauge",
            f'control_layer_proxy_latency_ms{{quantile="0.5"}} {snapshot.proxy.p50_ms}',
            f'control_layer_proxy_latency_ms{{quantile="0.95"}} {snapshot.proxy.p95_ms}',
            "# HELP control_layer_upstream_latency_ms Upstream provider latency percentiles "
            "in milliseconds.",
            "# TYPE control_layer_upstream_latency_ms gauge",
            f'control_layer_upstream_latency_ms{{quantile="0.5"}} {snapshot.upstream.p50_ms}',
            f'control_layer_upstream_latency_ms{{quantile="0.95"}} {snapshot.upstream.p95_ms}',
            "# HELP control_layer_overhead_ms Delay added by the control layer (proxy minus "
            "upstream) percentiles in milliseconds.",
            "# TYPE control_layer_overhead_ms gauge",
            f'control_layer_overhead_ms{{quantile="0.5"}} {snapshot.overhead.p50_ms}',
            f'control_layer_overhead_ms{{quantile="0.95"}} {snapshot.overhead.p95_ms}',
            "# HELP control_layer_cache_hit_ratio Decision cache hit ratio.",
            "# TYPE control_layer_cache_hit_ratio gauge",
            f"control_layer_cache_hit_ratio {snapshot.cache.hit_ratio}",
            "# HELP control_layer_calls_per_minute Calls processed per minute (last 60s).",
            "# TYPE control_layer_calls_per_minute gauge",
            f"control_layer_calls_per_minute {snapshot.calls_per_minute}",
        ]
        return "\n".join(lines) + "\n"
