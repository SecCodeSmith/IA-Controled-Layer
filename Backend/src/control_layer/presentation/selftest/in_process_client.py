from __future__ import annotations

import base64
import json
from typing import Any

from control_layer.application.selftest.agent_events import LLM_TARGET
from control_layer.application.selftest.scenario_client import StepObservation
from control_layer.application.use_cases.execute_approval import ExecuteApprovalUseCase
from control_layer.application.use_cases.handle_chat_completion import (
    HandleChatCompletionUseCase,
)
from control_layer.application.use_cases.handle_tool_call import HandleToolCallUseCase
from control_layer.application.use_cases.issue_token import IssueTokenUseCase
from control_layer.application.use_cases.outcomes import ToolCallOutcome
from control_layer.domain.exceptions import AgentUnavailableError, ControlLayerError
from control_layer.domain.models.chat import ChatCompletionRequest, ChatMessage
from control_layer.domain.models.enums import CallStatus
from control_layer.domain.models.tool import ToolCallRequest
from control_layer.domain.ports.model_provider import ModelProvider
from control_layer.domain.ports.token_verifier import TokenVerifier
from control_layer.presentation.api.error_handlers import describe_error

_EXPIRED_SHIFT_S = 2 * 28800


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def tamper_token(token: str, claim: str, value: Any) -> str:
    header, payload, signature = token.split(".")
    claims = json.loads(_unb64(payload))
    claims[claim] = value
    forged = _b64(json.dumps(claims, separators=(",", ":")).encode())
    return f"{header}.{forged}.{signature}"


def observation_from_outcome(
    outcome: ToolCallOutcome, target: str | None = None
) -> StepObservation:
    return StepObservation(
        http_status=202 if outcome.approval is not None else 200,
        status=outcome.status,
        stage=outcome.stage,
        rule_id=outcome.rule_id,
        reason=outcome.reason,
        approval_id=outcome.approval.id if outcome.approval is not None else None,
        target=target,
    )


def observation_from_error(
    exc: ControlLayerError, target: str | None = None
) -> StepObservation:
    fields = describe_error(exc)
    if fields is None:
        raise exc
    return StepObservation(
        http_status=fields.http_status,
        status=fields.status,
        stage=fields.stage,
        rule_id=fields.rule_id,
        reason=fields.reason,
        target=target,
    )


class InProcessScenarioClient:
    def __init__(
        self,
        chat_completion: HandleChatCompletionUseCase,
        tool_call: HandleToolCallUseCase,
        execute_approval: ExecuteApprovalUseCase,
        issue_token: IssueTokenUseCase,
        token_verifier: TokenVerifier,
        model_provider: ModelProvider,
    ) -> None:
        self._chat_completion = chat_completion
        self._tool_call = tool_call
        self._execute_approval = execute_approval
        self._issue_token = issue_token
        self._token_verifier = token_verifier
        self._model_provider = model_provider
        self._escalations: dict[str, StepObservation] = {}

    async def token_for(self, sub: str) -> str:
        return (await self._issue_token.execute(sub)).access_token

    async def tamper(self, token: str, claim: str, value: object) -> str:
        return tamper_token(token, claim, value)

    async def expired_token(self, sub: str) -> str:
        claims = (await self._issue_token.execute(sub)).claims
        past = claims.model_copy(
            update={"iat": claims.iat - _EXPIRED_SHIFT_S, "exp": claims.exp - _EXPIRED_SHIFT_S}
        )
        return await self._token_verifier.issue(past)

    async def chat(
        self,
        token: str,
        session_id: str,
        message: str,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> StepObservation:
        request = ChatCompletionRequest(
            model=model or self._model_provider.describe().model,
            messages=[ChatMessage(role="user", content=message)],
            max_tokens=max_tokens,
        )
        try:
            outcome = await self._chat_completion.execute(token, session_id, request)
        except ControlLayerError as exc:
            return observation_from_error(exc, LLM_TARGET)
        return StepObservation(
            http_status=200,
            status=outcome.status,
            stage=outcome.stage,
            rule_id=outcome.rule_id,
            reason=outcome.reason,
            target=LLM_TARGET,
        )

    async def tool_call(
        self, token: str, session_id: str, server: str, tool: str, arguments: dict
    ) -> StepObservation:
        request = ToolCallRequest(
            server=server, tool=tool, arguments=arguments, session_id=session_id
        )
        target = f"{server}.{tool}"
        try:
            outcome = await self._tool_call.execute(token, session_id, request)
        except ControlLayerError as exc:
            return observation_from_error(exc, target)
        observation = observation_from_outcome(outcome, target)
        if observation.approval_id is not None:
            self._escalations[observation.approval_id] = observation
        return observation

    def remember_escalations(self, observations: list[StepObservation]) -> None:
        for observation in observations:
            if observation.approval_id is not None:
                self._escalations[observation.approval_id] = observation

    async def approve(self, token: str, approval_id: str) -> StepObservation:
        try:
            outcome = await self._execute_approval.approve(token, approval_id)
        except ControlLayerError as exc:
            return observation_from_error(exc)
        escalation = self._escalations.pop(approval_id, None)
        executed = observation_from_outcome(
            outcome, escalation.target if escalation is not None else None
        )
        if escalation is None or executed.status == CallStatus.BLOCKED:
            return executed
        return escalation.model_copy(
            update={
                "http_status": executed.http_status,
                "approval_id": None,
                "reason": "Approved by the requesting user and executed once",
            }
        )

    async def agent_chat(
        self, token: str, session_id: str, prompt: str
    ) -> list[StepObservation]:
        raise AgentUnavailableError("agent tier requires the demo agent service")
