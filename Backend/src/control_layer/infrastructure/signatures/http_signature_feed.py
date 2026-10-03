from __future__ import annotations

import asyncio
import logging

import httpx

from control_layer.domain.models.signature import Signature

logger = logging.getLogger(__name__)


class HttpSignatureFeed:
    def __init__(self, url: str, client: httpx.AsyncClient | None = None) -> None:
        self._url = url
        self._client = client or httpx.AsyncClient()
        self._lock = asyncio.Lock()
        self._signatures: list[Signature] = []

    async def signatures(self) -> list[Signature]:
        async with self._lock:
            return list(self._signatures)

    async def reload(self) -> None:
        try:
            response = await self._client.get(self._url)
            response.raise_for_status()
            data = response.json()
            entries = data.get("signatures", []) if isinstance(data, dict) else data
            signatures = [Signature(**entry) for entry in entries]
        except Exception as exc:
            logger.error(
                "Failed to reload signature feed from %s, keeping last good set: %s",
                self._url,
                exc,
            )
            return
        async with self._lock:
            self._signatures = signatures
