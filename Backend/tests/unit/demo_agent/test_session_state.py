from __future__ import annotations

from demo_agent.session_store import SessionState


def _state_with(*contents: str) -> SessionState:
    state = SessionState()
    for content in contents:
        state.add_message({"role": "user", "content": content})
    return state


def test_rollback_to_truncates_messages_to_length() -> None:
    state = _state_with("a", "b", "c")

    state.rollback_to(1)

    assert [m["content"] for m in state.messages] == ["a"]


def test_rollback_to_current_length_or_beyond_is_noop() -> None:
    state = _state_with("a", "b")

    state.rollback_to(2)
    state.rollback_to(10)

    assert [m["content"] for m in state.messages] == ["a", "b"]
