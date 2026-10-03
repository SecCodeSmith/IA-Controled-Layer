from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from control_layer.domain.exceptions import AgentUnavailableError
from control_layer.domain.models.enums import CallStatus, StageName

__all__ = ["AgentUnavailableError", "ScenarioClient", "StepObservation"]


class StepObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    http_status: int
    status: CallStatus
    stage: StageName | None = None
    rule_id: str | None = None
    reason: str | None = None
    approval_id: str | None = None
    target: str | None = None


class ScenarioClient(Protocol):
    async def token_for(self, sub: str) -> str: ...

    async def tamper(self, token: str, claim: str, value: object) -> str: ...

    async def expired_token(self, sub: str) -> str: ...

    async def chat(
        self, token: str, session_id: str, message: str,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> StepObservation: ...

    async def tool_call(
        self, token: str, session_id: str, server: str, tool: str, arguments: dict
    ) -> StepObservation: ...

    async def approve(self, token: str, approval_id: str) -> StepObservation: ...

    async def agent_chat(
        self, token: str, session_id: str, prompt: str
    ) -> list[StepObservation]: ...
