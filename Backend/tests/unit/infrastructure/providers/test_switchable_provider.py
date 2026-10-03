from __future__ import annotations

from control_layer.domain.models.chat import ChatCompletionRequest, ChatMessage
from control_layer.infrastructure.providers.mock_provider import MockModelProvider
from control_layer.infrastructure.providers.openai_compatible_provider import (
    OpenAICompatibleModelProvider,
)
from control_layer.infrastructure.providers.switchable_provider import SwitchableModelProvider


async def test_switch_changes_describe_and_delegates_complete() -> None:
    switchable = SwitchableModelProvider(MockModelProvider())
    assert switchable.describe().name == "mock"

    switchable.switch(OpenAICompatibleModelProvider("http://x/v1", "gemma4:latest", "ollama"))

    assert switchable.describe().model == "gemma4:latest"
    switchable.switch(MockModelProvider())
    request = ChatCompletionRequest(
        model="mock", messages=[ChatMessage(role="user", content="hello")]
    )
    response = await switchable.complete(request)
    assert response.model == "mock"
