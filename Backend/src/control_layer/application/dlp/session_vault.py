from __future__ import annotations

import hashlib
import re
from collections.abc import Collection
from typing import Any

from control_layer.application.detectors.masking import PLACEHOLDER_NAMES
from control_layer.domain.ports.cache_repository import CacheRepository

_PLACEHOLDER_RE = re.compile(r"\[([A-Z_]+)_(\d+)\]")
_KIND_BY_NAME = {name: kind for kind, name in PLACEHOLDER_NAMES.items()}


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class SessionVault:
    def __init__(self, cache: CacheRepository) -> None:
        self._cache = cache

    @staticmethod
    def _value_key(scope: str, kind: str, value: str) -> str:
        return f"vault:{scope}:v:{kind}:{_digest(value)}"

    @staticmethod
    def _placeholder_key(scope: str, placeholder: str) -> str:
        return f"vault:{scope}:p:{placeholder}"

    @staticmethod
    def _scope(sub: str, session_id: str) -> str:
        return f"{_digest(sub)[:16]}:{session_id}"

    async def placeholder_for(
        self, session_id: str, kind: str, value: str, ttl_s: int, *, sub: str
    ) -> str:
        scope = self._scope(sub, session_id)
        value_key = self._value_key(scope, kind, value)
        existing = await self._cache.get(value_key)
        if existing is not None:
            return existing
        number = await self._cache.incr(f"vault:{scope}:n:{kind}", ttl_s)
        placeholder = f"[{PLACEHOLDER_NAMES[kind]}_{number}]"
        await self._cache.set(self._placeholder_key(scope, placeholder), value, ttl_s)
        await self._cache.set(value_key, placeholder, ttl_s)
        return placeholder

    async def restore(
        self, session_id: str, text: str, allowed_kinds: Collection[str], *, sub: str
    ) -> tuple[str, int]:
        if not allowed_kinds or "[" not in text:
            return text, 0
        scope = self._scope(sub, session_id)
        restored = 0
        pieces: list[str] = []
        cursor = 0
        for match in _PLACEHOLDER_RE.finditer(text):
            kind = _KIND_BY_NAME.get(match.group(1))
            if kind is None or kind not in allowed_kinds:
                continue
            value = await self._cache.get(self._placeholder_key(scope, match.group(0)))
            if value is None:
                continue
            pieces.append(text[cursor : match.start()])
            pieces.append(value)
            cursor = match.end()
            restored += 1
        pieces.append(text[cursor:])
        return "".join(pieces), restored

    async def restore_value(
        self, session_id: str, value: Any, allowed_kinds: Collection[str], *, sub: str
    ) -> tuple[Any, int]:
        if isinstance(value, str):
            return await self.restore(session_id, value, allowed_kinds, sub=sub)
        if isinstance(value, dict):
            result: dict[Any, Any] = {}
            total = 0
            for key, item in value.items():
                result[key], count = await self.restore_value(
                    session_id, item, allowed_kinds, sub=sub
                )
                total += count
            return result, total
        if isinstance(value, list):
            items: list[Any] = []
            total = 0
            for item in value:
                restored_item, count = await self.restore_value(
                    session_id, item, allowed_kinds, sub=sub
                )
                items.append(restored_item)
                total += count
            return items, total
        return value, 0
