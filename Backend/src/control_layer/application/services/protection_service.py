from __future__ import annotations

import json

from control_layer.domain.models.enums import ProtectionMode
from control_layer.domain.models.protection import ProtectionInfo
from control_layer.domain.ports.cache_repository import CacheRepository

MODE_KEY = "protection:mode"
OVERRIDES_KEY = "protection:rule_overrides"
_DECISION_PREFIX = "decision:"


class ProtectionService:
    def __init__(self, cache: CacheRepository) -> None:
        self._cache = cache

    async def get_mode(self) -> ProtectionMode:
        raw = await self._cache.get(MODE_KEY)
        try:
            return ProtectionMode(raw) if raw is not None else ProtectionMode.enforce
        except ValueError:
            return ProtectionMode.enforce

    async def set_mode(self, mode: ProtectionMode) -> None:
        await self._cache.set(MODE_KEY, mode.value)
        await self._flush_decisions()

    async def get_rule_overrides(self) -> dict[str, bool]:
        raw = await self._cache.get(OVERRIDES_KEY)
        if raw is None:
            return {}
        try:
            data = json.loads(raw)
        except ValueError:
            return {}
        return {str(k): bool(v) for k, v in data.items()} if isinstance(data, dict) else {}

    async def set_rule_override(self, rule_id: str, enabled: bool) -> None:
        overrides = await self.get_rule_overrides()
        overrides[rule_id] = enabled
        await self._cache.set(OVERRIDES_KEY, json.dumps(overrides))
        await self._flush_decisions()

    async def clear_overrides(self) -> None:
        await self._cache.delete(OVERRIDES_KEY)
        await self._flush_decisions()

    async def reset(self) -> None:
        await self._cache.delete(MODE_KEY)
        await self.clear_overrides()

    async def _flush_decisions(self) -> None:
        await self._cache.flush(_DECISION_PREFIX)


async def current_protection(service: ProtectionService | None) -> ProtectionInfo:
    if service is None:
        return ProtectionInfo()
    return ProtectionInfo(mode=await service.get_mode())
