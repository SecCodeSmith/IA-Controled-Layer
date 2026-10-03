from __future__ import annotations

import json
import re
import time
import uuid

from control_layer.domain.models.chat import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    FunctionCall,
    ToolCallSpec,
    Usage,
)
from control_layer.domain.models.provider import ProviderInfo

_FAKE_PAN = "4111111111111111"
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_LOGIN_FAIL_RE = re.compile(r"login tests|why did .* fail", re.IGNORECASE)
_DELETE_BRANCH_RE = re.compile(r"delete the stale branch", re.IGNORECASE)
_REPEAT_PROMPT_RE = re.compile(r"repeat (your )?system prompt", re.IGNORECASE)
_CARD_NUMBER_RE = re.compile(r"card number", re.IGNORECASE)
_SECURITY_JUDGE_RE = re.compile(r"security judge", re.IGNORECASE)


def _tool_call(call_id: str, name: str, arguments: dict[str, object]) -> ToolCallSpec:
    return ToolCallSpec(
        id=call_id,
        type="function",
        function=FunctionCall(name=name, arguments=json.dumps(arguments)),
    )


def _last_message(messages: list[ChatMessage], role: str) -> ChatMessage | None:
    for message in reversed(messages):
        if message.role == role:
            return message
    return None


def _first_message(messages: list[ChatMessage], role: str) -> ChatMessage | None:
    for message in messages:
        if message.role == role:
            return message
    return None


def _assistant_tool_call_turns(messages: list[ChatMessage]) -> int:
    return sum(1 for m in messages if m.role == "assistant" and m.tool_calls)


def _char_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class MockModelProvider:
    def describe(self) -> ProviderInfo:
        return ProviderInfo(name="mock", model="mock")

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        messages = request.messages

        system_message = _first_message(messages, "system")
        user_message = _last_message(messages, "user")
        system_text = (system_message.content if system_message else None) or ""
        user_text = (user_message.content if user_message else None) or ""
        turns_done = _assistant_tool_call_turns(messages)

        content: str | None = None
        tool_calls: list[ToolCallSpec] | None = None

        if _SECURITY_JUDGE_RE.search(system_text):
            content = json.dumps(
                {
                    "verdict": "allow",
                    "confidence": 0.1,
                    "reasoning": "mock judge: no attack pattern detected",
                }
            )
        elif _REPEAT_PROMPT_RE.search(user_text):
            content = system_text or "I have no system prompt to share."
        elif _CARD_NUMBER_RE.search(user_text):
            content = f"The card on file ends in {_FAKE_PAN[-4:]} (PAN: {_FAKE_PAN})."
        elif _LOGIN_FAIL_RE.search(user_text):
            if turns_done == 0:
                tool_calls = [
                    _tool_call(
                        f"call_{uuid.uuid4().hex[:8]}",
                        "ci.get_run",
                        {"pipeline": "e2e-login", "date": "2026-10-02"},
                    ),
                    _tool_call(
                        f"call_{uuid.uuid4().hex[:8]}",
                        "logs-db.query",
                        {"service": "auth", "since": "24h"},
                    ),
                ]
            elif turns_done == 1:
                tool_calls = [
                    _tool_call(
                        f"call_{uuid.uuid4().hex[:8]}",
                        "hr-db.find_approver",
                        {"request": "test-accounts"},
                    )
                ]
            else:
                content = (
                    "The e2e-login run failed due to an auth service error; "
                    "I was not able to reach HR to confirm a test account approver."
                )
        elif _DELETE_BRANCH_RE.search(user_text):
            if turns_done == 0:
                tool_calls = [
                    _tool_call(
                        f"call_{uuid.uuid4().hex[:8]}",
                        "github.delete_branch",
                        {"repo": "web-app", "branch": "feature/old-login"},
                    )
                ]
            else:
                content = "The branch deletion request has been submitted for approval."
        elif "send" in user_text.lower() and (email_match := _EMAIL_RE.search(user_text)):
            if turns_done == 0:
                recipient = email_match.group(0)
                tool_calls = [
                    _tool_call(
                        f"call_{uuid.uuid4().hex[:8]}",
                        "mail.send",
                        {
                            "to": recipient,
                            "subject": "Requested export",
                            "body": "Please find the requested information attached.",
                        },
                    )
                ]
            else:
                content = "The message has been sent."
        else:
            content = "I can help with that. Let me know if you need anything else."

        message = ChatMessage(role="assistant", content=content, tool_calls=tool_calls)

        prompt_tokens = _char_tokens(user_text or " ")
        completion_text = content if content is not None else json.dumps(
            [tc.model_dump() for tc in (tool_calls or [])]
        )
        completion_tokens = _char_tokens(completion_text)

        return ChatCompletionResponse(
            id=f"mockcmpl-{uuid.uuid4().hex[:12]}",
            object="chat.completion",
            created=int(time.time()),
            model="mock",
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=message,
                    finish_reason="tool_calls" if tool_calls else "stop",
                )
            ],
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )
