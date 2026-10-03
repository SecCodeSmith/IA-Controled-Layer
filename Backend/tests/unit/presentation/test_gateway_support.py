from __future__ import annotations

from types import SimpleNamespace

from control_layer.domain.exceptions import UpstreamProviderError
from control_layer.domain.models.chat import ChatCompletionRequest, ChatMessage
from control_layer.presentation.api.gateway_support import run_gateway_chat


async def test_upstream_failure_is_delivered_in_band() -> None:
    async def execute(token, session, request):
        error = UpstreamProviderError("upstream returned 404: model 'gpt-4-turbo' not found")
        error.call_id = "call-7"
        raise error

    container = SimpleNamespace(chat_completion=SimpleNamespace(execute=execute))
    request = ChatCompletionRequest(
        model="gpt-4-turbo", messages=[ChatMessage(role="user", content="hi")]
    )
    result = await run_gateway_chat(container, "t", "s", request)
    assert result.reply.content == (
        "[UPSTREAM ERROR] upstream returned 404: model 'gpt-4-turbo' not found"
    )
    assert result.reply.finish_reason == "error"
    assert result.reply.prompt_tokens == result.reply.completion_tokens == 0
    assert result.control_layer["call_id"] == "call-7"
