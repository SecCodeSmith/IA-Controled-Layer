from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from control_layer.domain.exceptions import ControlLayerError
from control_layer.domain.models.enums import CallStatus, StageName


class StepObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    http_status: int
    status: CallStatus
    stage: StageName | None = None
    rule_id: str | None = None
    reason: str | None = None
    approval_id: str | None = None


class AgentUnavailableError(ControlLayerError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ScenarioClient(Protocol):
    async def token_for(self, sub: str) -> str: ...

    async def tamper(self, token: str, claim: str, value: object) -> str: ...

    async def expired_token(self, sub: str) -> str: ...

    async def chat(
        self, token: str, session_id: str, message: str, model: str | None = None
    ) -> StepObservation: ...

    async def tool_call(
        self, token: str, session_id: str, server: str, tool: str, arguments: dict
    ) -> StepObservation: ...

    async def approve(self, token: str, approval_id: str) -> StepObservation: ...

    async def agent_chat(
        self, token: str, session_id: str, prompt: str
    ) -> list[StepObservation]: ...
