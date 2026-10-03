from control_layer.domain.models.audit import CallLatency


def test_overhead_is_proxy_time_minus_upstream_time() -> None:
    latency = CallLatency(proxy_ms=12.5, upstream_ms=10.0)

    assert latency.overhead_ms == 2.5


def test_overhead_never_goes_below_zero() -> None:
    latency = CallLatency(proxy_ms=1.0, upstream_ms=3.0)

    assert latency.overhead_ms == 0.0


def test_overhead_equals_total_when_nothing_went_upstream() -> None:
    latency = CallLatency(proxy_ms=4.2, upstream_ms=0.0)

    assert latency.overhead_ms == 4.2


def test_overhead_is_serialised_with_the_latency() -> None:
    latency = CallLatency(proxy_ms=12.5, upstream_ms=10.0, stages={"dlp": 0.3})

    assert latency.model_dump()["overhead_ms"] == 2.5
    assert CallLatency.model_validate(latency.model_dump()).overhead_ms == 2.5
