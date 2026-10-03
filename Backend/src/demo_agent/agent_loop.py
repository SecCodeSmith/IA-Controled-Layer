"""The demo agent's OpenAI-style tool loop, driven entirely through the
control layer (`WIKI/api-contract.md`, section "Demo agent service").

Every model completion and every tool call goes through the control layer,
so the model being driven here is the one the control layer governs. This
module holds no knowledge of control_layer internals: it only speaks the
contract's HTTP/JSON shapes via `ControlLayerClient`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, timedelta

from demo_agent.control_layer_client import ControlLayerClient, ControlLayerDenied
from demo_agent.schemas import (
    AgentBudget,
    ApprovalRequiredEvent,
    AssistantTextEvent,
    ChatCompletionRequest,
    Event,
    Identity,
    NoticeEvent,
    ToolCall,
    ToolCallDecision,
    ToolCallEvent,
    ToolCallRequest,
)
from demo_agent.session_store import PendingApproval, SessionState, SessionStore
from demo_agent.settings import Settings
from demo_agent.tool_mapping import parse_function_name, to_openai_tools


class UnknownApprovalError(Exception):
    def __init__(self, approval_id: str) -> None:
        super().__init__(f"no pending approval {approval_id!r} for this session")
        self.approval_id = approval_id


def _system_prompt(identity: Identity, today: date) -> str:
    yesterday = today - timedelta(days=1)
    return (
        f"You are a bank employee assistant for {identity.name} "
        f"({identity.role}, {identity.location}). "
        f"Today is {today.isoformat()}; use ISO dates (YYYY-MM-DD). "
        f'"Last night" or "yesterday" means {yesterday.isoformat()}. '
        "Use the provided tools to answer the user's questions. "
        "Tool hints: CI pipelines are named like e2e-login and runs are fetched with "
        "ci.get_run(pipeline, date). Service logs are in logs-db.query(service, since) "
        "with services auth, payments and web. HR approvals are looked up with "
        "hr-db.find_approver(request). "
        "Calling one tool at a time is fine. "
        "Never say you did something (deleted, pushed, sent, transferred, read) unless you "
        "called the matching tool in this turn and saw its result. When the user asks for an "
        "action that a tool can do, call the tool; do not answer from memory. "
        "If the control layer blocks or masks something, tell the user plainly "
        "and suggest what to do next. Be concise."
    )


class AgentLoop:
    def __init__(
        self,
        client: ControlLayerClient,
        sessions: SessionStore,
        settings: Settings,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._client = client
        self._sessions = sessions
        self._settings = settings
        self._today = today

    async def run_turn(self, token: str, session_id: str, user_message: str) -> list[Event]:
        me = await self._client.me(token, session_id=session_id)
        tool_descriptors = await self._client.list_tools(
            token, session_id=session_id, scope=self._settings.tool_scope
        )

        session = self._sessions.get_or_create(session_id)
        if not session.messages:
            prompt = _system_prompt(me.identity, self._today())
            session.add_message({"role": "system", "content": prompt})
        session.model = me.provider.model
        session.openai_tools = to_openai_tools(tool_descriptors)
        session.add_message({"role": "user", "content": user_message})

        return await self._drive_loop(token, session_id, session)

    async def resume_after_approval(
        self,
        token: str,
        session_id: str,
        approval_id: str,
        decision: ToolCallDecision,
    ) -> list[Event]:
        session = self._sessions.get(session_id)
        if (
            session is None
            or session.pending_approval is None
            or session.pending_approval.approval_id != approval_id
        ):
            raise UnknownApprovalError(approval_id)

        pending = session.pending_approval
        session.pending_approval = None
        events: list[Event] = []

        if decision == "approve":
            events.append(await self._apply_approval(token, session_id, pending))
        else:
            await self._client.reject(token, approval_id, session_id=session_id)
            session.add_message(
                {
                    "role": "tool",
                    "tool_call_id": pending.tool_call_id,
                    "content": "The user rejected this action.",
                }
            )

        events.extend(await self._drive_loop(token, session_id, session))
        return events

    async def _apply_approval(
        self, token: str, session_id: str, pending: PendingApproval
    ) -> ToolCallEvent:
        outcome = await self._client.approve(token, pending.approval_id, session_id=session_id)
        content_text = outcome.result.content_text if outcome.result else ""
        event = ToolCallEvent(
            call_id=outcome.call_id,
            tool=pending.qualified_tool,
            arguments=pending.arguments,
            status=outcome.status,
            stage=outcome.stage,
            rule_id=outcome.rule_id,
            reason=outcome.reason,
            items_masked=outcome.items_masked or 0,
            result_preview=content_text[:200] if content_text else None,
        )
        session = self._sessions.get(session_id)
        if session is not None:
            session.add_message(
                {"role": "tool", "tool_call_id": pending.tool_call_id, "content": content_text}
            )
        return event

    async def _drive_loop(self, token: str, session_id: str, session: SessionState) -> list[Event]:
        events: list[Event] = []
        for _ in range(self._settings.max_iterations):
            request = ChatCompletionRequest(
                model=session.model or "",
                messages=session.messages,
                tools=session.openai_tools,
                tool_choice="auto",
                temperature=self._settings.temperature,
            )
            try:
                completion = await self._client.chat_completion(
                    token, request, session_id=session_id
                )
            except ControlLayerDenied as denied:
                events.append(
                    NoticeEvent(
                        status=denied.status or "BLOCKED",
                        stage=denied.stage,
                        rule_id=denied.rule_id,
                        reason=denied.reason,
                    )
                )
                return events

            choice = completion.choices[0]
            message = choice.message
            session.add_message(message.model_dump(exclude_none=True))

            if not message.tool_calls:
                control = completion.control_layer
                events.append(
                    AssistantTextEvent(
                        text=message.content or "",
                        status=control.status,
                        stage=control.stage,
                        rule_id=control.rule_id,
                        reason=control.reason,
                    )
                )
                return events

            awaiting_approval = await self._handle_tool_calls(
                token, session_id, session, message.tool_calls, events
            )
            if awaiting_approval:
                return events

        events.append(
            NoticeEvent(
                status="FLAGGED",
                reason=(
                    f"Stopped after {self._settings.max_iterations} model turns "
                    "without a final answer."
                ),
            )
        )
        return events

    async def _handle_tool_calls(
        self,
        token: str,
        session_id: str,
        session: SessionState,
        tool_calls: list[ToolCall],
        events: list[Event],
    ) -> bool:
        for tool_call in tool_calls:
            try:
                server, tool_name = parse_function_name(tool_call.function.name)
            except ValueError as exc:
                session.add_message(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": f"Invalid tool name: {exc}",
                    }
                )
                continue

            try:
                arguments = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError as exc:
                session.add_message(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": f"Invalid tool call arguments JSON: {exc}",
                    }
                )
                continue

            qualified = f"{server}.{tool_name}"
            try:
                outcome = await self._client.call_tool(
                    token,
                    ToolCallRequest(
                        server=server, tool=tool_name, arguments=arguments, session_id=session_id
                    ),
                    session_id=session_id,
                )
            except ControlLayerDenied as denied:
                events.append(
                    ToolCallEvent(
                        call_id=denied.call_id or "",
                        tool=qualified,
                        arguments=arguments,
                        status=denied.status or "BLOCKED",
                        stage=denied.stage,
                        rule_id=denied.rule_id,
                        reason=denied.reason,
                        items_masked=0,
                        result_preview=None,
                    )
                )
                blocked_message = (
                    f"Blocked by the control layer: {denied.reason} "
                    f"({denied.stage} · {denied.rule_id})"
                )
                session.add_message(
                    {"role": "tool", "tool_call_id": tool_call.id, "content": blocked_message}
                )
                continue

            if outcome.approval is not None:
                events.append(
                    ApprovalRequiredEvent(
                        approval_id=outcome.approval.id,
                        tool=qualified,
                        arguments=arguments,
                        rule_id=outcome.rule_id,
                        reason=outcome.reason,
                    )
                )
                session.pending_approval = PendingApproval(
                    approval_id=outcome.approval.id,
                    tool_call_id=tool_call.id,
                    qualified_tool=qualified,
                    arguments=arguments,
                )
                return True

            content_text = outcome.result.content_text if outcome.result else ""
            events.append(
                ToolCallEvent(
                    call_id=outcome.call_id,
                    tool=qualified,
                    arguments=arguments,
                    status=outcome.status,
                    stage=outcome.stage,
                    rule_id=outcome.rule_id,
                    reason=outcome.reason,
                    items_masked=outcome.items_masked or 0,
                    result_preview=content_text[:200] if content_text else None,
                )
            )
            session.add_message(
                {"role": "tool", "tool_call_id": tool_call.id, "content": content_text}
            )

        return False


async def fetch_agent_budget(
    client: ControlLayerClient, token: str, session_id: str
) -> AgentBudget:
    me = await client.me(token, session_id=session_id)
    return AgentBudget(tokens_used=me.budget.tokens_used, tokens_limit=me.budget.tokens_limit)
