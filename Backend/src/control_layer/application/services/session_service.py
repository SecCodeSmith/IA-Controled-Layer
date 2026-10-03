from __future__ import annotations

from control_layer.domain.models.session import SessionState
from control_layer.domain.ports.session_repository import SessionRepository


class SessionService:
    def __init__(self, session_repository: SessionRepository) -> None:
        self._session_repository = session_repository

    async def load(self, session_id: str) -> SessionState:
        return await self._session_repository.get(session_id)

    async def save(self, state: SessionState) -> None:
        await self._session_repository.save(state)
