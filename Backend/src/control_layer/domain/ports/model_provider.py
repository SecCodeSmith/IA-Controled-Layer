from __future__ import annotations

from typing import Protocol

from control_layer.domain.models.chat import ChatCompletionRequest, ChatCompletionResponse
from control_layer.domain.models.provider import ProviderInfo


class ModelProvider(Protocol):
    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse: ...

    def describe(self) -> ProviderInfo: ...
