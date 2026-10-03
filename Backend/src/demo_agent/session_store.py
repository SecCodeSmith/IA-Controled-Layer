"""Bounded in-memory per-session conversation state.

Not durable and not shared across processes; good enough for a single
uvicorn worker demo. Bounded on two axes: the number of concurrent sessions
(oldest evicted first) and the number of messages kept per session (the
leading system prompt is always preserved).
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

DEFAULT_MAX_SESSIONS = 200
DEFAULT_MAX_MESSAGES = 200


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
    def __init__(self, max_sessions: int = DEFAULT_MAX_SESSIONS) -> None:
        self._max_sessions = max_sessions
        self._sessions: OrderedDict[str, SessionState] = OrderedDict()

    def get(self, session_id: str) -> SessionState | None:
        session = self._sessions.get(session_id)
        if session is not None:
            self._sessions.move_to_end(session_id)
        return session

    def get_or_create(self, session_id: str) -> SessionState:
        session = self._sessions.get(session_id)
        if session is None:
            session = SessionState()
            self._sessions[session_id] = session
            if len(self._sessions) > self._max_sessions:
                self._sessions.popitem(last=False)
        self._sessions.move_to_end(session_id)
        return session
