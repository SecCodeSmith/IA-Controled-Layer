"""Bounded in-memory per-session conversation state.

Not durable and not shared across processes; good enough for a single
uvicorn worker demo. Bounded on two axes: the number of concurrent sessions
(oldest evicted first) and the number of messages kept per session (the
leading system prompt is always preserved).
"""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

DEFAULT_MAX_SESSIONS = 200
DEFAULT_MAX_MESSAGES = 200
DEFAULT_TTL_S = 3600.0


@dataclass
class PendingApproval:
    approval_id: str
    tool_call_id: str
    qualified_tool: str
    arguments: dict[str, Any]


@dataclass
class SessionState:
    messages: list[dict[str, Any]] = field(default_factory=list)
    model: str | None = None
    openai_tools: list[dict[str, Any]] = field(default_factory=list)
    pending_approval: PendingApproval | None = None
    protection_mode: str | None = None
    last_used: float = 0.0

    def forget_conversation(self) -> None:
        self.messages = []
        self.pending_approval = None

    def rollback_to(self, length: int) -> None:
        del self.messages[length:]

    def add_message(
        self, message: dict[str, Any], max_messages: int = DEFAULT_MAX_MESSAGES
    ) -> None:
        self.messages.append(message)
        if len(self.messages) <= max_messages:
            return
        has_system = bool(self.messages) and self.messages[0].get("role") == "system"
        head = self.messages[:1] if has_system else []
        keep = max_messages - len(head)
        self.messages = head + self.messages[-keep:]


class SessionStore:
    def __init__(
        self,
        max_sessions: int = DEFAULT_MAX_SESSIONS,
        ttl_s: float = DEFAULT_TTL_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_sessions = max_sessions
        self._ttl_s = ttl_s
        self._clock = clock
        self._sessions: OrderedDict[tuple[str, str], SessionState] = OrderedDict()

    def get(self, sub: str, session_id: str) -> SessionState | None:
        key = (sub, session_id)
        session = self._sessions.get(key)
        if session is None:
            return None
        if self._expired(session):
            del self._sessions[key]
            return None
        session.last_used = self._clock()
        self._sessions.move_to_end(key)
        return session

    def get_or_create(self, sub: str, session_id: str) -> SessionState:
        session = self.get(sub, session_id)
        if session is None:
            self._sweep()
            session = SessionState(last_used=self._clock())
            self._sessions[(sub, session_id)] = session
            if len(self._sessions) > self._max_sessions:
                self._sessions.popitem(last=False)
        return session

    def reset(self, sub: str, session_id: str) -> None:
        self._sessions.pop((sub, session_id), None)

    def _expired(self, session: SessionState) -> bool:
        return self._clock() - session.last_used > self._ttl_s

    def _sweep(self) -> None:
        for key in [k for k, v in self._sessions.items() if self._expired(v)]:
            del self._sessions[key]
