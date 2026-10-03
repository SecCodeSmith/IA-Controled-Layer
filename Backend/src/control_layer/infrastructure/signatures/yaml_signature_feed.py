from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import yaml

from control_layer.domain.models.signature import Signature

logger = logging.getLogger(__name__)


class YamlSignatureFeed:
    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._lock = asyncio.Lock()
        self._signatures: list[Signature] = []
        self._load_sync()

    def _load_sync(self) -> None:
        if not self._path.exists():
            logger.warning("Signature feed file not found: %s", self._path)
            return
        try:
            raw_yaml = self._path.read_text(encoding="utf-8")
            data = yaml.safe_load(raw_yaml) or {}
            entries = data.get("signatures", [])
            signatures = [Signature(**entry) for entry in entries]
        except Exception as exc:
            logger.error(
                "Failed to load signature feed from %s, keeping last good set: %s",
                self._path,
                exc,
            )
            return
        self._signatures = signatures

    async def signatures(self) -> list[Signature]:
        async with self._lock:
            return list(self._signatures)

    async def reload(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._load_sync)
