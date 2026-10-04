from __future__ import annotations

import pytest

from demo_agent.agent_loop import AgentLoop
from demo_agent.session_store import PendingApproval, SessionStore

from .conftest import ANNA_IDENTITY, ScriptedBackend, completion_body, me_body, ok


def _me_for(sub: str) -> tuple[int, dict]:
    body = me_body()
    body["identity"] = {**ANNA_IDENTITY, "sub": sub, "name": sub}
    return ok(body)


@pytest.fixture
def agent_loop(control_layer_client, session_store, settings) -> AgentLoop:
    return AgentLoop(client=control_layer_client, sessions=session_store, settings=settings)


async def test_same_session_id_with_two_subs_is_independent(
    agent_loop: AgentLoop, backend: ScriptedBackend, session_store: SessionStore
) -> None:
    for sub, text in (("anna", "anna secret"), ("bob", "bob question")):
        backend.me_queue.append(_me_for(sub))
        backend.completion_queue.append(ok(completion_body(content="ok")))
        await agent_loop.run_turn("t", "shared-id", text)

    anna = session_store.get("anna", "shared-id")
    bob = session_store.get("bob", "shared-id")
    assert anna is not bob
    assert any(m.get("content") == "anna secret" for m in anna.messages)
    assert all(m.get("content") != "anna secret" for m in bob.messages)


def test_idle_session_expires_on_access_and_sweeps_on_create() -> None:
    now = [0.0]
    store = SessionStore(ttl_s=10, clock=lambda: now[0])
    store.get_or_create("a", "s1").add_message({"role": "user", "content": "x"})
    store.get_or_create("a", "s2")

    now[0] = 5.0
    assert store.get("a", "s1") is not None
    now[0] = 12.0
    assert store.get("a", "s2") is None
    assert store.get("a", "s1") is not None
    now[0] = 30.0
    store.get_or_create("b", "s3")
    assert len(store._sessions) == 1
    assert store.get("a", "s1") is None


async def test_reset_endpoint_clears_messages_and_pending_approval(
    test_client, backend: ScriptedBackend, test_app
) -> None:
    store: SessionStore = test_app.state.sessions
    session = store.get_or_create("anna.kowalska", "s-r")
    session.add_message({"role": "user", "content": "hi"})
    session.pending_approval = PendingApproval("ap", "tc", "gh.x", {})

    response = test_client.post(
        "/agent/sessions/s-r/reset", headers={"Authorization": "Bearer t"}
    )

    assert response.status_code == 200
    assert response.json() == {"session_id": "s-r", "cleared": True}
    assert store.get("anna.kowalska", "s-r") is None


def test_reset_requires_bearer(test_client) -> None:
    assert test_client.post("/agent/sessions/s-r/reset").status_code == 401
