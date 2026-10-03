from __future__ import annotations

import itertools
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from control_layer.application.use_cases.outcomes import ChatCompletionOutcome
from control_layer.domain.models.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    FunctionCall,
    ToolCallSpec,
)

CHUNK_WORDS = 6
BLOCKED_PREFIX = "[BLOCKED by AI Control Layer]"
UPSTREAM_ERROR_PREFIX = "[UPSTREAM ERROR]"
_WORD_RE = re.compile(r"\S+\s*")


@dataclass(frozen=True)
class GatewayReply:
    content: str
    tool_calls: list[ToolCallSpec] = field(default_factory=list)
    finish_reason: str = "stop"
    prompt_tokens: int = 0
    completion_tokens: int = 0


def blocked_text(stage: str | None, rule_id: str | None, reason: str | None) -> str:
    where = " · ".join(part for part in (stage, rule_id) if part)
    detail = reason or "request blocked"
    return f"{BLOCKED_PREFIX} {where}: {detail}" if where else f"{BLOCKED_PREFIX} {detail}"


def blocked_reply(stage: str | None, rule_id: str | None, reason: str | None) -> GatewayReply:
    return GatewayReply(content=blocked_text(stage, rule_id, reason), finish_reason="blocked")


def upstream_error_reply(reason: str | None) -> GatewayReply:
    text = f"{UPSTREAM_ERROR_PREFIX} {reason or 'upstream provider failed'}"
    return GatewayReply(content=text, finish_reason="error")


def reply_from_response(response: ChatCompletionResponse) -> GatewayReply:
    choice = response.choices[0]
    return GatewayReply(
        content=choice.message.content or "",
        tool_calls=list(choice.message.tool_calls or []),
        finish_reason=choice.finish_reason or "stop",
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens,
    )


def split_chunks(text: str, words: int = CHUNK_WORDS) -> list[str]:
    tokens = _WORD_RE.findall(text)
    return ["".join(tokens[i : i + words]) for i in range(0, len(tokens), words)]


def now_rfc3339() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def ms_to_ns(ms: float) -> int:
    return int(ms * 1_000_000)


def _request_extras(body: dict[str, Any]) -> dict[str, Any]:
    options = body.get("options")
    options = options if isinstance(options, dict) else {}
    extras: dict[str, Any] = {}
    if options.get("temperature") is not None:
        extras["temperature"] = options["temperature"]
    if options.get("num_predict") is not None:
        extras["max_tokens"] = options["num_predict"]
    if body.get("format") == "json":
        extras["response_format"] = {"type": "json_object"}
    return extras


def ollama_chat_to_request(body: dict[str, Any]) -> ChatCompletionRequest:
    counter = itertools.count(1)
    last_ids: dict[str, str] = {}
    messages: list[ChatMessage] = []
    for raw in body.get("messages") or []:
        tool_calls: list[ToolCallSpec] | None = None
        if raw.get("tool_calls"):
            tool_calls = []
            for call in raw["tool_calls"]:
                function = call.get("function") or {}
                call_id = f"call_{next(counter)}"
                name = function.get("name", "")
                last_ids[name] = call_id
                arguments = function.get("arguments", {})
                if not isinstance(arguments, str):
                    arguments = json.dumps(arguments if arguments is not None else {})
                tool_calls.append(
                    ToolCallSpec(id=call_id, function=FunctionCall(name=name, arguments=arguments))
                )
        role = raw.get("role", "user")
        tool_name = raw.get("tool_name") if role == "tool" else None
        messages.append(
            ChatMessage(
                role=role,
                content=raw.get("content"),
                tool_calls=tool_calls,
                name=tool_name,
                tool_call_id=last_ids.get(tool_name or "", "call_0") if role == "tool" else None,
            )
        )
    return ChatCompletionRequest(
        model=body.get("model", ""),
        messages=messages,
        tools=body.get("tools") or None,
        stream=False,
        **_request_extras(body),
    )


def ollama_generate_to_request(body: dict[str, Any]) -> ChatCompletionRequest:
    messages: list[ChatMessage] = []
    if body.get("system"):
        messages.append(ChatMessage(role="system", content=body["system"]))
    messages.append(ChatMessage(role="user", content=body.get("prompt", "")))
    return ChatCompletionRequest(
        model=body.get("model", ""), messages=messages, stream=False, **_request_extras(body)
    )


def _ollama_tool_calls(calls: list[ToolCallSpec]) -> list[dict[str, Any]]:
    result = []
    for call in calls:
        try:
            arguments = json.loads(call.function.arguments or "{}")
        except ValueError:
            arguments = {}
        result.append({"function": {"name": call.function.name, "arguments": arguments}})
    return result


def _final_counts(reply: GatewayReply, total_ns: int, eval_ns: int) -> dict[str, Any]:
    return {
        "done": True,
        "done_reason": reply.finish_reason,
        "total_duration": total_ns,
        "load_duration": 0,
        "prompt_eval_count": reply.prompt_tokens,
        "prompt_eval_duration": 0,
        "eval_count": reply.completion_tokens,
        "eval_duration": eval_ns,
    }


def ollama_chat_response(
    model: str, reply: GatewayReply, total_ns: int, eval_ns: int
) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": reply.content}
    if reply.tool_calls:
        message["tool_calls"] = _ollama_tool_calls(reply.tool_calls)
    return {
        "model": model,
        "created_at": now_rfc3339(),
        "message": message,
        **_final_counts(reply, total_ns, eval_ns),
    }


def ollama_chat_stream(
    model: str, reply: GatewayReply, total_ns: int, eval_ns: int
) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = [
        {
            "model": model,
            "created_at": now_rfc3339(),
            "message": {"role": "assistant", "content": chunk},
            "done": False,
        }
        for chunk in split_chunks(reply.content)
    ]
    if reply.tool_calls:
        lines.append(
            {
                "model": model,
                "created_at": now_rfc3339(),
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": _ollama_tool_calls(reply.tool_calls),
                },
                "done": False,
            }
        )
    lines.append(
        {
            "model": model,
            "created_at": now_rfc3339(),
            "message": {"role": "assistant", "content": ""},
            **_final_counts(reply, total_ns, eval_ns),
        }
    )
    return lines


def ollama_generate_response(
    model: str, reply: GatewayReply, total_ns: int, eval_ns: int
) -> dict[str, Any]:
    return {
        "model": model,
        "created_at": now_rfc3339(),
        "response": reply.content,
        "context": [],
        **_final_counts(reply, total_ns, eval_ns),
    }


def ollama_generate_stream(
    model: str, reply: GatewayReply, total_ns: int, eval_ns: int
) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = [
        {"model": model, "created_at": now_rfc3339(), "response": chunk, "done": False}
        for chunk in split_chunks(reply.content)
    ]
    lines.append(
        {
            "model": model,
            "created_at": now_rfc3339(),
            "response": "",
            "context": [],
            **_final_counts(reply, total_ns, eval_ns),
        }
    )
    return lines


def ndjson(lines: list[dict[str, Any]]) -> list[str]:
    return [json.dumps(line, ensure_ascii=False) + "\n" for line in lines]


def control_layer_extension(outcome: ChatCompletionOutcome) -> dict[str, Any]:
    return {
        "call_id": outcome.call_id,
        "status": outcome.status.value,
        "stage": outcome.stage.value if outcome.stage else None,
        "rule_id": outcome.rule_id,
        "reason": outcome.reason,
        "items_masked": outcome.items_masked,
        "proxy_latency_ms": outcome.proxy_latency_ms,
        "upstream_latency_ms": outcome.upstream_latency_ms,
    }


def sse_frame(payload: dict[str, Any] | str) -> str:
    data = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return f"data: {data}\n\n"


def openai_stream_frames(
    model: str,
    reply: GatewayReply,
    control_layer: dict[str, Any] | None = None,
    completion_id: str | None = None,
) -> list[str]:
    cid = completion_id or f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    def chunk(delta: dict[str, Any], finish: str | None, **extra: Any) -> dict[str, Any]:
        return {
            "id": cid,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            **extra,
        }

    frames = [
        sse_frame(chunk({"role": "assistant", "content": text}, None))
        for text in split_chunks(reply.content)
    ]
    if not frames:
        frames.append(sse_frame(chunk({"role": "assistant", "content": ""}, None)))
    for index, call in enumerate(reply.tool_calls):
        function = {"name": call.function.name, "arguments": call.function.arguments}
        delta = {
            "tool_calls": [
                {"index": index, "id": call.id, "type": "function", "function": function}
            ]
        }
        frames.append(sse_frame(chunk(delta, None)))
    final_extra: dict[str, Any] = {
        "usage": {
            "prompt_tokens": reply.prompt_tokens,
            "completion_tokens": reply.completion_tokens,
            "total_tokens": reply.prompt_tokens + reply.completion_tokens,
        }
    }
    if control_layer is not None:
        final_extra["control_layer"] = control_layer
    finish = reply.finish_reason
    if reply.tool_calls and finish == "stop":
        finish = "tool_calls"
    frames.append(sse_frame(chunk({}, finish, **final_extra)))
    frames.append(sse_frame("[DONE]"))
    return frames
