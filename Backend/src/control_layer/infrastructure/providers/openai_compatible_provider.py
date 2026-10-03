from __future__ import annotations

from typing import Any

import httpx

from control_layer.domain.exceptions import UpstreamProviderError
from control_layer.domain.models.chat import ChatCompletionRequest, ChatCompletionResponse
from control_layer.domain.models.provider import ProviderInfo

_PASSTHROUGH_FIELDS = ("tools", "tool_choice", "response_format", "max_tokens")


class OpenAICompatibleModelProvider:
    def __init__(
        self,
        base_url: str,
        model: str,
        provider_name: str = "openai_compatible",
        api_key: str | None = None,
        timeout_s: float = 30.0,
        keep_alive: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._provider_name = provider_name
        self._api_key = api_key
        self._timeout_s = timeout_s
        self._keep_alive = keep_alive
        self._client = client or httpx.AsyncClient()

    def describe(self) -> ProviderInfo:
        return ProviderInfo(name=self._provider_name, model=self._model)

    def _build_body(self, request: ChatCompletionRequest) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": request.model,
            "messages": [m.model_dump(exclude_none=True) for m in request.messages],
            "temperature": request.temperature,
        }
        for field_name in _PASSTHROUGH_FIELDS:
            value = getattr(request, field_name, None)
            if value is not None:
                body[field_name] = value
        if self._keep_alive is not None:
            body["keep_alive"] = self._keep_alive
        return body

    @staticmethod
    def _map_usage(data: dict[str, Any]) -> None:
        usage = data.get("usage")
        if not isinstance(usage, dict):
            return
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        usage.setdefault("prompt_tokens", prompt_tokens)
        usage.setdefault("completion_tokens", completion_tokens)
        usage.setdefault("total_tokens", prompt_tokens + completion_tokens)

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        body = self._build_body(request)
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}

        try:
            response = await self._client.post(
                f"{self._base_url}/chat/completions",
                json=body,
                headers=headers,
                timeout=self._timeout_s,
            )
        except httpx.TimeoutException as exc:
            raise UpstreamProviderError(f"upstream timeout: {exc}") from exc
        except httpx.HTTPError as exc:
            raise UpstreamProviderError(f"upstream request failed: {exc}") from exc

        if response.status_code >= 400:
            raise UpstreamProviderError(
                f"upstream returned {response.status_code}: {response.text}"
            )

        data = response.json()
        self._map_usage(data)
        return ChatCompletionResponse.model_validate(data)
