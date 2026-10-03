from __future__ import annotations

import logging

import httpx

from control_layer.domain.models.model_info import ModelInfo

logger = logging.getLogger(__name__)

_BYTES_PER_GB = 1_000_000_000


class OllamaModelDirectory:
    def __init__(
        self,
        base_url: str,
        timeout_s: float = 2.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._client = client

    async def list_models(self) -> list[ModelInfo]:
        return [*await self._ollama_models(), ModelInfo(provider="mock", model="mock")]

    async def _ollama_models(self) -> list[ModelInfo]:
        try:
            payload = await self._fetch_tags()
        except Exception as exc:
            logger.warning("Ollama model listing unavailable at %s (%s)", self._base_url, exc)
            return []
        return [
            ModelInfo(
                provider="ollama",
                model=entry["name"],
                size_gb=self._size_gb(entry.get("size")),
            )
            for entry in payload.get("models", [])
            if entry.get("name")
        ]

    async def _fetch_tags(self) -> dict:
        client = self._client or httpx.AsyncClient()
        try:
            response = await client.get(f"{self._base_url}/api/tags", timeout=self._timeout_s)
            response.raise_for_status()
            return response.json()
        finally:
            if self._client is None:
                await client.aclose()

    @staticmethod
    def _size_gb(size_bytes: object) -> float | None:
        if not isinstance(size_bytes, int | float):
            return None
        return round(size_bytes / _BYTES_PER_GB, 1)
