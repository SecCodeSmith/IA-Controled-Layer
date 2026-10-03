from __future__ import annotations

import os
from typing import Any
from collections.abc import Awaitable, Callable

from control_layer.application.selftest.scenario_executor import ScenarioExecutor, ScenarioResult
from control_layer.application.use_cases.execute_approval import ExecuteApprovalUseCase
from control_layer.application.use_cases.handle_chat_completion import (
    HandleChatCompletionUseCase,
)
from control_layer.application.use_cases.handle_tool_call import HandleToolCallUseCase
from control_layer.application.use_cases.issue_token import IssueTokenUseCase
from control_layer.domain.ports.model_provider import ModelProvider
from control_layer.domain.ports.token_verifier import TokenVerifier
from control_layer.infrastructure.settings import Settings
from control_layer.presentation.selftest.http_agent_client import AgentTierScenarioClient
from control_layer.presentation.selftest.in_process_client import InProcessScenarioClient


class IsolatedExecutor:
    def __init__(
        self, inner: ScenarioExecutor, reset_state: Callable[[], Awaitable[None]]
    ) -> None:
        self._inner = inner
        self._reset_state = reset_state

    async def run(self, scenario: Any, tier: str = "scripted") -> ScenarioResult:
        await self._reset_state()
        return await self._inner.run(scenario, tier=tier)


def build_executor_factory(
    settings: Settings,
    chat_completion: HandleChatCompletionUseCase,
    tool_call: HandleToolCallUseCase,
    execute_approval: ExecuteApprovalUseCase,
    issue_token: IssueTokenUseCase,
    token_verifier: TokenVerifier,
    model_provider: ModelProvider,
    reset_state: Callable[[], Awaitable[None]],
) -> Callable[[str], IsolatedExecutor]:
    agent_url = os.environ.get("CTRL_AGENT_URL", "http://localhost:8090")
    parts = (
        chat_completion,
        tool_call,
        execute_approval,
        issue_token,
        token_verifier,
        model_provider,
    )

    def factory(agent: str) -> IsolatedExecutor:
        if agent == "ollama":
            client = AgentTierScenarioClient(*parts, agent_url=agent_url)
        else:
            client = InProcessScenarioClient(*parts)
        return IsolatedExecutor(ScenarioExecutor(client), reset_state)

    return factory
