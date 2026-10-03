from __future__ import annotations

import httpx

from control_layer.infrastructure.providers.ollama_model_directory import OllamaModelDirectory


def _directory(handler) -> OllamaModelDirectory:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OllamaModelDirectory("http://ollama:11434", client=client)


async def test_lists_ollama_tags_with_sizes_and_always_includes_mock() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={
                "models": [
                    {"name": "qwen2.5:7b", "size": 4_683_000_000},
                    {"name": "gemma4:latest", "size": 6_600_000_000},
                    {"size": 1},
                ]
            },
        )

    models = await _directory(handler).list_models()

    assert [(m.provider, m.model, m.size_gb) for m in models] == [
        ("ollama", "qwen2.5:7b", 4.7),
        ("ollama", "gemma4:latest", 6.6),
        ("mock", "mock", None),
    ]


async def test_unreachable_ollama_yields_only_mock() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    models = await _directory(handler).list_models()

    assert [(m.provider, m.model) for m in models] == [("mock", "mock")]


async def test_error_status_yields_only_mock() -> None:
    models = await _directory(lambda request: httpx.Response(500)).list_models()

    assert [m.provider for m in models] == ["mock"]
