from __future__ import annotations

from typing import Protocol

from control_layer.domain.models.session import SessionState


class SessionRepository(Protocol):
    async def get(self, session_id: str) -> SessionState: ...

    async def save(self, state: SessionState) -> None: ...

    async def clear(self, session_id: str | None = None) -> None: ...
