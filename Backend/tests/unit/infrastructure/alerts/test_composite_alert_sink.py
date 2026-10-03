from __future__ import annotations

import logging

import pytest

from control_layer.infrastructure.alerts.composite_alert_sink import CompositeAlertSink


class _RecordingSink:
    def __init__(self) -> None:
        self.received: list[dict] = []

    async def emit(self, alert: dict) -> None:
        self.received.append(alert)


class _FailingSink:
    async def emit(self, alert: dict) -> None:
        raise RuntimeError("sink is down")


async def test_fans_out_to_all_sinks() -> None:
    sink1, sink2 = _RecordingSink(), _RecordingSink()
    composite = CompositeAlertSink([sink1, sink2])

    await composite.emit({"id": "al_1"})

    assert sink1.received == [{"id": "al_1"}]
    assert sink2.received == [{"id": "al_1"}]


async def test_survives_a_failing_sink(caplog: pytest.LogCaptureFixture) -> None:
    good_sink = _RecordingSink()
    composite = CompositeAlertSink([_FailingSink(), good_sink])

    with caplog.at_level(logging.ERROR):
        await composite.emit({"id": "al_1"})

    assert good_sink.received == [{"id": "al_1"}]
    assert any("sink is down" in record.message for record in caplog.records)


async def test_all_sinks_failing_does_not_raise() -> None:
    composite = CompositeAlertSink([_FailingSink(), _FailingSink()])

    await composite.emit({"id": "al_1"})
