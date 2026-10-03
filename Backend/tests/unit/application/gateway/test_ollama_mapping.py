from __future__ import annotations

import json

from control_layer.application.gateway import ollama_mapping as m
from control_layer.domain.models.chat import (
    ChatCompletionChoice,
    ChatCompletionResponse,
    ChatMessage,
    FunctionCall,
    ToolCallSpec,
    Usage,
)


def test_chat_request_maps_options_format_and_tools() -> None:
    request = m.ollama_chat_to_request(
        {
            "model": "qwen2.5:7b",
            "messages": [{"role": "user", "content": "hi", "images": ["abc"]}],
            "tools": [{"type": "function", "function": {"name": "f"}}],
            "format": "json",
            "options": {"temperature": 0.2, "num_predict": 64},
            "keep_alive": "5m",
        }
    )
    assert request.model == "qwen2.5:7b"
    assert request.temperature == 0.2
    assert request.max_tokens == 64
    assert request.response_format == {"type": "json_object"}
    assert request.tools == [{"type": "function", "function": {"name": "f"}}]
    assert request.stream is False
    assert request.messages[0].content == "hi"


def test_chat_request_encodes_tool_calls_and_tool_results() -> None:
    request = m.ollama_chat_to_request(
        {
            "model": "m",
            "messages": [
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "a", "arguments": {"x": 1}}},
                        {"function": {"name": "b", "arguments": {}}},
                    ],
                },
                {"role": "tool", "content": "42", "tool_name": "b"},
            ],
        }
    )
    calls = request.messages[0].tool_calls
    assert [c.id for c in calls] == ["call_1", "call_2"]
    assert json.loads(calls[0].function.arguments) == {"x": 1}
    tool = request.messages[1]
    assert tool.role == "tool"
    assert tool.content == "42"
    assert tool.tool_call_id == "call_2"


def test_generate_request_builds_system_and_user_messages() -> None:
    request = m.ollama_generate_to_request(
        {"model": "m", "prompt": "p", "system": "s", "options": {"num_predict": 5}}
    )
    assert [(x.role, x.content) for x in request.messages] == [("system", "s"), ("user", "p")]
    assert request.max_tokens == 5


def test_split_chunks_groups_six_words_and_roundtrips() -> None:
    text = "one two three four five six seven eight\nnine"
    chunks = m.split_chunks(text)
    assert chunks == ["one two three four five six ", "seven eight\nnine"]
    assert "".join(chunks) == text
    assert m.split_chunks("") == []


def _response(content: str | None, tool_calls: list[ToolCallSpec] | None = None):
    return ChatCompletionResponse(
        id="chatcmpl-1",
        created=1,
        model="mock",
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=content, tool_calls=tool_calls),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=3, completion_tokens=4, total_tokens=7),
    )


def test_chat_response_shape() -> None:
    reply = m.reply_from_response(_response("hello there"))
    body = m.ollama_chat_response("mock", reply, 5_000, 2_000)
    assert body["message"] == {"role": "assistant", "content": "hello there"}
    assert body["done"] is True
    assert body["done_reason"] == "stop"
    assert body["prompt_eval_count"] == 3
    assert body["eval_count"] == 4
    assert body["total_duration"] == 5_000
    assert body["eval_duration"] == 2_000
    assert body["created_at"].endswith("Z")


def test_chat_response_tool_calls_have_object_arguments() -> None:
    call = ToolCallSpec(id="c1", function=FunctionCall(name="f", arguments='{"a": 1}'))
    reply = m.reply_from_response(_response(None, [call]))
    body = m.ollama_chat_response("mock", reply, 1, 1)
    assert body["message"]["tool_calls"] == [{"function": {"name": "f", "arguments": {"a": 1}}}]


def test_chat_stream_ends_with_done_and_counts() -> None:
    reply = m.reply_from_response(_response("a b c d e f g h"))
    lines = m.ollama_chat_stream("mock", reply, 10, 5)
    assert [x["done"] for x in lines] == [False, False, True]
    assert lines[0]["message"]["content"] == "a b c d e f "
    assert lines[-1]["eval_count"] == 4
    assert all(line.endswith("\n") for line in m.ndjson(lines))


def test_chat_stream_carries_tool_calls_in_one_chunk() -> None:
    call = ToolCallSpec(id="c1", function=FunctionCall(name="f", arguments="{}"))
    reply = m.reply_from_response(_response(None, [call]))
    lines = m.ollama_chat_stream("mock", reply, 1, 1)
    assert lines[0]["message"]["tool_calls"][0]["function"]["name"] == "f"
    assert lines[-1]["done"] is True


def test_generate_response_and_stream() -> None:
    reply = m.reply_from_response(_response("x y"))
    single = m.ollama_generate_response("mock", reply, 1, 1)
    assert single["response"] == "x y"
    assert single["context"] == []
    assert single["done"] is True
    lines = m.ollama_generate_stream("mock", reply, 1, 1)
    assert lines[0]["response"] == "x y"
    assert lines[0]["done"] is False
    assert lines[-1]["done"] is True


def test_blocked_text_and_reply() -> None:
    assert (
        m.blocked_text("policy", "R1", "no way")
        == "[BLOCKED by AI Control Layer] policy · R1: no way"
    )
    reply = m.blocked_reply("policy", "R1", "no way")
    assert reply.finish_reason == "blocked"
    assert reply.prompt_tokens == reply.completion_tokens == 0
    assert m.ollama_chat_response("mock", reply, 1, 0)["done_reason"] == "blocked"


def test_openai_stream_frames_framing_and_final_chunk() -> None:
    reply = m.reply_from_response(_response("a b c d e f g"))
    frames = m.openai_stream_frames("mock", reply, {"call_id": "c-1"}, "chatcmpl-x")
    assert all(f.startswith("data: ") and f.endswith("\n\n") for f in frames)
    assert frames[-1] == "data: [DONE]\n\n"
    first = json.loads(frames[0][6:])
    assert first["object"] == "chat.completion.chunk"
    assert first["choices"][0]["delta"] == {"role": "assistant", "content": "a b c d e f "}
    assert first["choices"][0]["finish_reason"] is None
    final = json.loads(frames[-2][6:])
    assert final["choices"][0]["finish_reason"] == "stop"
    assert final["usage"] == {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}
    assert final["control_layer"] == {"call_id": "c-1"}


def test_openai_stream_tool_call_deltas() -> None:
    call = ToolCallSpec(id="c1", function=FunctionCall(name="f", arguments='{"a":1}'))
    reply = m.reply_from_response(_response(None, [call]))
    frames = m.openai_stream_frames("mock", reply)
    delta = json.loads(frames[1][6:])["choices"][0]["delta"]
    assert delta["tool_calls"] == [
        {
            "index": 0,
            "id": "c1",
            "type": "function",
            "function": {"name": "f", "arguments": '{"a":1}'},
        }
    ]
    assert json.loads(frames[-2][6:])["choices"][0]["finish_reason"] == "tool_calls"


def test_openai_stream_blocked_message() -> None:
    frames = m.openai_stream_frames("mock", m.blocked_reply("dlp", "R9", "secret"))
    first = json.loads(frames[0][6:])
    assert first["choices"][0]["delta"]["content"].startswith(m.BLOCKED_PREFIX)
    assert json.loads(frames[-2][6:])["choices"][0]["finish_reason"] == "blocked"
