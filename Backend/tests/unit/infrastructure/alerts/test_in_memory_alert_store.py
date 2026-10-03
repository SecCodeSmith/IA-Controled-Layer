from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from control_layer.domain.models.alert import Alert, AlertUserRef
from control_layer.infrastructure.alerts.in_memory_alert_store import InMemoryAlertStore


def _alert(**overrides) -> dict:
    base = {
        "id": "al_1",
        "created_at": "2026-10-03T10:41:40Z",
        "call_id": "c_1",
        "user": {"sub": "anna.kowalska", "name": "Anna Kowalska", "role": "developer"},
        "status": "MASKED",
        "stage": "dlp",
        "rule_id": "pii_masking",
    }
    base.update(overrides)
    return base


async def test_add_then_list_recent() -> None:
    store = InMemoryAlertStore()
    await store.add(_alert(id="al_1"))
    await store.add(_alert(id="al_2"))

    items = await store.list_recent(limit=10)

    assert [item["id"] for item in items] == ["al_2", "al_1"]


async def test_list_recent_respects_limit() -> None:
    store = InMemoryAlertStore()
    for i in range(5):
        await store.add(_alert(id=f"al_{i}"))

    items = await store.list_recent(limit=2)

    assert [item["id"] for item in items] == ["al_4", "al_3"]


async def test_list_recent_filters_by_user() -> None:
    store = InMemoryAlertStore()
    anna = {"sub": "anna.kowalska", "name": "A", "role": "developer"}
    marek = {"sub": "marek.nowak", "name": "M", "role": "hr"}
    await store.add(_alert(id="al_1", user=anna))
    await store.add(_alert(id="al_2", user=marek))

    items = await store.list_recent(limit=10, user="marek.nowak")

    assert [item["id"] for item in items] == ["al_2"]


async def test_list_recent_filters_by_rule_id() -> None:
    store = InMemoryAlertStore()
    await store.add(_alert(id="al_1", rule_id="pii_masking"))
    await store.add(_alert(id="al_2", rule_id="rate_limit"))

    items = await store.list_recent(limit=10, rule_id="rate_limit")

    assert [item["id"] for item in items] == ["al_2"]


async def test_bounded_deque_drops_oldest() -> None:
    store = InMemoryAlertStore(max_size=3)
    for i in range(5):
        await store.add(_alert(id=f"al_{i}"))

    items = await store.list_recent(limit=10)

    assert [item["id"] for item in items] == ["al_4", "al_3", "al_2"]


async def test_subscribe_receives_new_alerts() -> None:
    store = InMemoryAlertStore()
    subscription = store.subscribe()

    await store.add(_alert(id="al_1"))

    received = await asyncio.wait_for(anext(subscription), timeout=1)
    assert received["id"] == "al_1"


async def test_subscribe_does_not_receive_alerts_added_before_subscribing() -> None:
    store = InMemoryAlertStore()
    await store.add(_alert(id="al_before"))

    subscription = store.subscribe()
    await store.add(_alert(id="al_after"))

    received = await asyncio.wait_for(anext(subscription), timeout=1)
    assert received["id"] == "al_after"


async def test_multiple_subscribers_each_receive_alert() -> None:
    store = InMemoryAlertStore()
    sub1 = store.subscribe()
    sub2 = store.subscribe()

    await store.add(_alert(id="al_1"))

    received1 = await asyncio.wait_for(anext(sub1), timeout=1)
    received2 = await asyncio.wait_for(anext(sub2), timeout=1)
    assert received1["id"] == "al_1"
    assert received2["id"] == "al_1"


def _real_alert(**overrides: object) -> Alert:
    base = {
        "id": "al_real",
        "created_at": datetime(2026, 10, 3, 10, 41, 40, tzinfo=UTC),
        "call_id": "c_1",
        "user": AlertUserRef(sub="anna.kowalska", name="Anna Kowalska", role="developer"),
        "status": "MASKED",
        "stage": "dlp",
        "rule_id": "pii_masking",
        "severity": "medium",
        "reason": "3 email addresses masked",
    }
    base.update(overrides)
    return Alert(**base)


async def test_accepts_real_domain_alert_model() -> None:
    store = InMemoryAlertStore()
    await store.add(_real_alert())

    items = await store.list_recent(limit=10, user="anna.kowalska", rule_id="pii_masking")

    assert len(items) == 1
    assert items[0].id == "al_real"


async def test_clear_empties_the_store() -> None:
    store = InMemoryAlertStore()
    await store.add(_alert(id="al_1"))
    await store.add(_alert(id="al_2"))

    await store.clear()

    assert await store.list_recent(limit=10) == []


async def test_clear_keeps_subscribers_connected() -> None:
    store = InMemoryAlertStore()
    await store.add(_alert(id="al_before"))
    subscription = store.subscribe()

    await store.clear()
    await store.add(_alert(id="al_after"))

    received = await asyncio.wait_for(anext(subscription), timeout=1)
    assert received["id"] == "al_after"

    items = await store.list_recent(limit=10)
    assert [item["id"] for item in items] == ["al_after"]
