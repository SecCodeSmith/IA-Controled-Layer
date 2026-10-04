"""Direct AgentLoop tests: narrow edge cases that don't need the FastAPI
layer. The broader end-to-end turns (two tool calls, blocked, escalation,
approve/reject resume, denied completion, budget) live in test_main.py and
exercise the same AgentLoop through the real app.
"""

from __future__ import annotations

import json

import pytest

from demo_agent.agent_loop import AgentLoop
from demo_agent.schemas import AssistantTextEvent, NoticeEvent

from .conftest import (
    ScriptedBackend,
    completion_body,
    me_body,
    ok,
    tool_call_function,
    tool_descriptor,
    tool_outcome_body,
    tools_body,
)


@pytest.fixture
def agent_loop(control_layer_client, session_store, settings) -> AgentLoop:
    return AgentLoop(client=control_layer_client, sessions=session_store, settings=settings)


async def test_invalid_tool_arguments_json_handled(
    agent_loop: AgentLoop, backend: ScriptedBackend
) -> None:
    backend.tools_response = tools_body(tool_descriptor("ci", "get_run"))
    backend.completion_queue.append(
        ok(
            completion_body(
                tool_calls=[tool_call_function("ci__get_run", "not-valid-json", call_id="call_bad")]
            )
        )
    )
    backend.completion_queue.append(ok(completion_body(content="Sorry, I could not run that.")))

    events = await agent_loop.run_turn("token-1", "s-1", "please check ci")

    assert backend.requests_to("/v1/tools/call") == []
    assert len(events) == 1
    assert isinstance(events[0], AssistantTextEvent)
    assert events[0].text == "Sorry, I could not run that."

    second_request = json.loads(backend.requests_to("/v1/chat/completions")[1].content)
    tool_messages = [m for m in second_request["messages"] if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert tool_messages[0]["tool_call_id"] == "call_bad"
    assert "Invalid tool call arguments JSON" in tool_messages[0]["content"]


async def test_invalid_tool_function_name_handled(
    agent_loop: AgentLoop, backend: ScriptedBackend
) -> None:
    backend.tools_response = tools_body(tool_descriptor("ci", "get_run"))
    backend.completion_queue.append(
        ok(
            completion_body(
                tool_calls=[tool_call_function("not_qualified", {}, call_id="call_bad")]
            )
        )
    )
    backend.completion_queue.append(ok(completion_body(content="Sorry, that tool is unknown.")))

    events = await agent_loop.run_turn("token-1", "s-x", "do something odd")

    assert backend.requests_to("/v1/tools/call") == []
    assert len(events) == 1
    assert events[0].text == "Sorry, that tool is unknown."


async def test_iteration_cap_exhausted(
    agent_loop: AgentLoop, backend: ScriptedBackend, settings
) -> None:
    backend.tools_response = tools_body(tool_descriptor("ci", "get_run"))
    for index in range(settings.max_iterations):
        backend.completion_queue.append(
            ok(
                completion_body(
                    tool_calls=[
                        tool_call_function(
                            "ci__get_run",
                            {"pipeline": "x", "date": "2026-10-02"},
                            call_id=f"call_{index}",
                        )
                    ]
                )
            )
        )
        backend.tool_call_queue.append(
            ok(tool_outcome_body(call_id=f"c_{index}", status="ALLOWED", content_text="ok"))
        )

    events = await agent_loop.run_turn("token-1", "s-2", "loop forever please")

    assert len(backend.requests_to("/v1/chat/completions")) == settings.max_iterations
    assert len(events) == settings.max_iterations + 1
    assert isinstance(events[-1], NoticeEvent)
    assert events[-1].status == "FLAGGED"
    assert "model turns" in (events[-1].reason or "")


async def test_requests_all_tool_scope_and_injects_date_into_prompt(
    control_layer_client, session_store, settings, backend: ScriptedBackend
) -> None:
    from datetime import date

    loop = AgentLoop(
        client=control_layer_client,
        sessions=session_store,
        settings=settings,
        today=lambda: date(2026, 10, 3),
    )
    backend.tools_response = tools_body(tool_descriptor("ci", "get_run"))
    backend.completion_queue.append(ok(completion_body(content="hi")))

    await loop.run_turn("token-1", "s-scope", "why did login tests fail last night?")

    assert backend.requests_to("/v1/tools")[0].url.query == b"scope=all"
    system = json.loads(backend.requests_to("/v1/chat/completions")[0].content)["messages"][0]
    assert "2026-10-03" in system["content"]
    assert "2026-10-02" in system["content"]
    assert "ci.get_run(pipeline, date)" in system["content"]
    assert "logs-db.query(service, since)" in system["content"]


def _mem(store):  # noqa: ANN001, ANN202
    return store.get("anna.kowalska", "s-mem")


def _me_with_mode(mode: str) -> tuple[int, dict]:
    body = me_body()
    body["protection"] = {"mode": mode, "changed_at": "2026-10-04T10:00:00Z"}
    return ok(body)


_CLEARED_PREFIX = "Conversation memory cleared"


async def _hr_turn(agent_loop: AgentLoop, backend: ScriptedBackend, mode: str) -> list:
    backend.me_queue.append(_me_with_mode(mode))
    backend.tools_response = tools_body(tool_descriptor("hr-db", "query"))
    backend.completion_queue.append(
        ok(completion_body(tool_calls=[tool_call_function("hr-db__query", {"query": "all"})]))
    )
    backend.tool_call_queue.append(
        ok(tool_outcome_body(call_id="c_t", status="ALLOWED", content_text="salary rows"))
    )
    backend.completion_queue.append(ok(completion_body(content="done")))
    return await agent_loop.run_turn("token-1", "s-mem", "show salaries")


async def test_memory_cleared_when_protection_tightens_from_off(
    agent_loop: AgentLoop, backend: ScriptedBackend, session_store
) -> None:
    await _hr_turn(agent_loop, backend, "off")
    assert any(m.get("content") == "salary rows" for m in _mem(session_store).messages)

    backend.me_queue.append(_me_with_mode("enforce"))
    backend.completion_queue.append(ok(completion_body(content="fresh")))
    events = await agent_loop.run_turn("token-1", "s-mem", "what were the salaries?")

    assert isinstance(events[0], NoticeEvent)
    assert events[0].status == "FLAGGED"
    assert events[0].reason.startswith(_CLEARED_PREFIX)
    last_request = json.loads(backend.requests_to("/v1/chat/completions")[-1].content)
    assert all("salary rows" not in str(m.get("content")) for m in last_request["messages"])
    assert [m["role"] for m in last_request["messages"]] == ["system", "user"]
    assert _mem(session_store).protection_mode == "enforce"


async def test_memory_cleared_when_monitor_tightens_to_enforce(
    agent_loop: AgentLoop, backend: ScriptedBackend, session_store
) -> None:
    await _hr_turn(agent_loop, backend, "monitor")
    backend.me_queue.append(_me_with_mode("enforce"))
    backend.completion_queue.append(ok(completion_body(content="fresh")))

    events = await agent_loop.run_turn("token-1", "s-mem", "again")

    assert isinstance(events[0], NoticeEvent)


async def test_memory_kept_when_mode_unchanged_or_loosens(
    agent_loop: AgentLoop, backend: ScriptedBackend, session_store
) -> None:
    await _hr_turn(agent_loop, backend, "enforce")
    backend.me_queue.append(_me_with_mode("enforce"))
    backend.completion_queue.append(ok(completion_body(content="same")))
    same = await agent_loop.run_turn("token-1", "s-mem", "again")
    backend.me_queue.append(_me_with_mode("off"))
    backend.completion_queue.append(ok(completion_body(content="loose")))
    loosened = await agent_loop.run_turn("token-1", "s-mem", "and again")

    assert not any(isinstance(e, NoticeEvent) for e in same + loosened)
    assert any(m.get("content") == "salary rows" for m in _mem(session_store).messages)


async def test_first_turn_with_unknown_mode_only_stores_it(
    agent_loop: AgentLoop, backend: ScriptedBackend, session_store
) -> None:
    seeded = session_store.get_or_create("anna.kowalska", "s-mem")
    seeded.add_message({"role": "tool", "content": "old"})
    backend.me_queue.append(_me_with_mode("enforce"))
    backend.completion_queue.append(ok(completion_body(content="hi")))

    events = await agent_loop.run_turn("token-1", "s-mem", "hello")

    assert not any(isinstance(e, NoticeEvent) for e in events)
    assert _mem(session_store).protection_mode == "enforce"
    assert any(m.get("content") == "old" for m in _mem(session_store).messages)
