from __future__ import annotations

from control_layer.domain.models.chat import ChatCompletionRequest, ChatCompletionResponse
from control_layer.domain.models.provider import ProviderInfo
from control_layer.domain.ports.model_provider import ModelProvider


class SwitchableModelProvider:
    def __init__(self, initial: ModelProvider) -> None:
        self._active = initial

    def switch(self, provider: ModelProvider) -> None:
        self._active = provider

    def describe(self) -> ProviderInfo:
        return self._active.describe()

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        return await self._active.complete(request)
