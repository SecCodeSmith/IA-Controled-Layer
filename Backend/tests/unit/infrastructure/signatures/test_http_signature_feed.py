from __future__ import annotations

import httpx

from control_layer.infrastructure.signatures.http_signature_feed import HttpSignatureFeed

SIGNATURE_PAYLOAD = {
    "signatures": [
        {
            "id": "SIG-001",
            "title": "Ignore previous instructions",
            "pattern": "ignore previous instructions",
            "categories": ["prompt_injection"],
            "severity": "high",
            "points": ["prompt"],
        }
    ]
}


def _client_for(handler: object) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_starts_empty_before_first_reload() -> None:
    feed = HttpSignatureFeed("https://example.com/signatures", client=_client_for(
        lambda request: httpx.Response(200, json=SIGNATURE_PAYLOAD)
    ))

    assert await feed.signatures() == []


async def test_reload_fetches_and_parses_signatures() -> None:
    feed = HttpSignatureFeed(
        "https://example.com/signatures",
        client=_client_for(lambda request: httpx.Response(200, json=SIGNATURE_PAYLOAD)),
    )

    await feed.reload()
    signatures = await feed.signatures()

    assert len(signatures) == 1
    assert signatures[0].id == "SIG-001"


async def test_reload_keeps_last_good_on_http_error() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(200, json=SIGNATURE_PAYLOAD)
        return httpx.Response(500, text="boom")

    feed = HttpSignatureFeed("https://example.com/signatures", client=_client_for(handler))
    await feed.reload()
    await feed.reload()

    signatures = await feed.signatures()
    assert len(signatures) == 1
    assert signatures[0].id == "SIG-001"


async def test_reload_keeps_last_good_on_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    feed = HttpSignatureFeed("https://example.com/signatures", client=_client_for(handler))
    await feed.reload()

    assert await feed.signatures() == []
