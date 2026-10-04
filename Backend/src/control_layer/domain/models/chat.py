from __future__ import annotations

from pydantic import BaseModel, ConfigDict

PROMPT_TURN_SEPARATOR = "\n␞\n"


class FunctionCall(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    arguments: str


class ToolCallSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    type: str = "function"
    function: FunctionCall


class ChatMessage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    role: str
    content: str | None = None
    tool_calls: list[ToolCallSpec] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    model: str
    messages: list[ChatMessage]
    tools: list[dict] | None = None
    tool_choice: str | dict | None = None
    temperature: float = 1.0
    max_tokens: int | None = None
    response_format: dict | None = None
    stream: bool = False


class Usage(BaseModel):
    model_config = ConfigDict(frozen=True)

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionChoice(BaseModel):
    model_config = ConfigDict(frozen=True)

    index: int
    message: ChatMessage
    finish_reason: str | None = None


class ChatCompletionResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: Usage
