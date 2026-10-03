from __future__ import annotations

from pydantic import BaseModel


class StageMetric(BaseModel):
    p50_ms: float
    p95_ms: float
    count: int


class LatencyBand(BaseModel):
    p50_ms: float
    p95_ms: float


class CacheMetric(BaseModel):
    hits: int
    misses: int
    hit_ratio: float


class MetricsResponse(BaseModel):
    stages: dict[str, StageMetric] = {}
    proxy: LatencyBand
    upstream: LatencyBand
    cache: CacheMetric
    calls_per_minute: float
