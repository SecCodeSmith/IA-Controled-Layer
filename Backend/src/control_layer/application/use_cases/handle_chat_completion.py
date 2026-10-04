from __future__ import annotations

import asyncio
import re
import time

from control_layer.application.audit.call_record_builder import CallRecordBuilder
from control_layer.application.auth.identity_service import IdentityService
from control_layer.application.pipeline.processing_pipeline import ProcessingPipeline
from control_layer.application.services.audit_service import AuditService
from control_layer.application.services.budget_service import BudgetService
from control_layer.application.services.call_id_generator import CallIdGenerator
from control_layer.application.services.circuit_breaker_service import CircuitBreakerService
from control_layer.application.services.risk_service import RiskService
from control_layer.application.services.session_service import SessionService
from control_layer.application.use_cases.outcomes import ChatCompletionOutcome
from control_layer.domain.exceptions import (
    BudgetExceededError,
    ControlLayerError,
    PolicyViolationError,
    QuarantinedError,
    RateLimitedError,
    UpstreamProviderError,
)
from control_layer.domain.models.audit import TokensInfo
from control_layer.domain.models.chat import (
    PROMPT_TURN_SEPARATOR,
    ChatCompletionRequest,
    ChatMessage,
    Usage,
)
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import Decision, merge_action, status_for
from control_layer.domain.models.enums import CallKind, InterceptionPoint, RuleAction, StageName
from control_layer.domain.models.identity import Identity
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.ports.model_provider import ModelProvider
from control_layer.domain.ports.policy_repository import PolicyRepository

_BLOCKING_ACTIONS = (RuleAction.block, RuleAction.quarantine, RuleAction.require_approval)
_PLACEHOLDER_RE = re.compile(r"\[[A-Z0-9_]+_\d+\]")


def _count_placeholders(text: str | None) -> int:
    return len(_PLACEHOLDER_RE.findall(text)) if text else 0


def _combine(decision1: Decision, decision2: Decision | None) -> Decision:
    if decision2 is None:
        return decision1
    violations = list(decision1.violations) + list(decision2.violations)
    action = merge_action([decision1.action, decision2.action])
    return Decision(
        status=status_for(action),
        action=action,
        violations=violations,
        stage_results=list(decision1.stage_results) + list(decision2.stage_results),
        stage_timings_ms={**decision1.stage_timings_ms, **decision2.stage_timings_ms},
    )


def _outcome_fields(
    decision: Decision,
) -> tuple[StageName | None, str | None, str | None, list[str]]:
    primary = decision.primary_violation
    if primary is not None:
        return primary.stage, primary.rule_id, primary.reason, primary.owasp
    structural = next((r for r in decision.stage_results if r.action != RuleAction.allow), None)
    if structural is not None:
        return structural.stage, None, structural.reason, []
    return None, None, None, []


class HandleChatCompletionUseCase:
    def __init__(
        self,
        pipeline: ProcessingPipeline,
        identity_service: IdentityService,
        model_provider: ModelProvider,
        budget_service: BudgetService,
        session_service: SessionService,
        audit_service: AuditService,
        circuit_breaker: CircuitBreakerService,
        risk_service: RiskService,
        call_ids: CallIdGenerator,
        policy_repository: PolicyRepository,
        canary_token: str,
    ) -> None:
        self._pipeline = pipeline
        self._identity_service = identity_service
        self._model_provider = model_provider
        self._budget_service = budget_service
        self._session_service = session_service
        self._audit_service = audit_service
        self._circuit_breaker = circuit_breaker
        self._risk_service = risk_service
        self._call_ids = call_ids
        self._policy_repository = policy_repository
        self._canary_token = canary_token
        self._record_builder = CallRecordBuilder()

    async def execute(
        self, token: str, session_id: str | None, request: ChatCompletionRequest
    ) -> ChatCompletionOutcome:
        start = time.perf_counter()
        call_id = await self._call_ids.next()
        policy = await self._policy_repository.current()

        identity = await self._identity_service.resolve(token, session_id or "")
        resolved_session_id = session_id or identity.sub
        if session_id is None:
            identity = identity.model_copy(update={"session_id": resolved_session_id})

        session_state = await self._session_service.load(resolved_session_id)
        turns = _prompt_turns(request)

        ctx1 = ProcessingContext(
            identity=identity,
            point=InterceptionPoint.prompt,
            text=PROMPT_TURN_SEPARATOR.join(turns),
            chat=request,
            session_id=resolved_session_id,
            call_id=call_id,
            metadata={
                "token": token,
                "model": request.model,
                "max_tokens": request.max_tokens,
                "session_state": session_state,
                "latest_user_text": _latest_user_text(request),
                "prompt_turns": len(turns),
            },
        )
        decision1 = await self._pipeline.run(ctx1)

        if decision1.action in _BLOCKING_ACTIONS:
            proxy_latency_ms = (time.perf_counter() - start) * 1000
            await self._finish_failed_call(
                identity=identity,
                call_id=call_id,
                decision=decision1,
                request=request,
                proxy_latency_ms=proxy_latency_ms,
                upstream_latency_ms=0.0,
            )
            raise self._mapped_error(decision1, call_id)

        forward_request = _apply_masked_prompt(request, ctx1.masked_text)
        forward_request = _append_canary(forward_request, self._canary_token, policy)
        final_max_tokens = ctx1.metadata.get("max_tokens")
        forward_request = forward_request.model_copy(update={"max_tokens": final_max_tokens})

        upstream_start = time.perf_counter()
        try:
            response = await asyncio.wait_for(
                self._model_provider.complete(forward_request),
                timeout=policy.budgets.upstream_timeout_s,
            )
        except TimeoutError as exc:
            upstream_latency_ms = (time.perf_counter() - upstream_start) * 1000
            proxy_latency_ms = (time.perf_counter() - start) * 1000
            error = UpstreamProviderError("Upstream provider timed out")
            error.call_id = call_id
            await self._finish_failed_call(
                identity=identity,
                call_id=call_id,
                decision=decision1,
                request=request,
                proxy_latency_ms=proxy_latency_ms,
                upstream_latency_ms=upstream_latency_ms,
                error_reason=error.args[0] if error.args else "upstream error",
            )
            raise error from exc
        except ControlLayerError as exc:
            exc.call_id = call_id
            upstream_latency_ms = (time.perf_counter() - upstream_start) * 1000
            proxy_latency_ms = (time.perf_counter() - start) * 1000
            await self._finish_failed_call(
                identity=identity,
                call_id=call_id,
                decision=decision1,
                request=request,
                proxy_latency_ms=proxy_latency_ms,
                upstream_latency_ms=upstream_latency_ms,
                error_reason=str(exc),
            )
            raise
        upstream_latency_ms = (time.perf_counter() - upstream_start) * 1000

        await self._budget_service.record(identity, response.usage, request.model, policy)

        assistant_text = response.choices[0].message.content or ""
        ctx2 = ProcessingContext(
            identity=identity,
            point=InterceptionPoint.response,
            text=assistant_text,
            chat=forward_request,
            session_id=resolved_session_id,
            call_id=call_id,
            metadata={
                "token": token,
                "model": request.model,
                "max_tokens": final_max_tokens,
                "session_state": session_state,
                "upstream_usage": response.usage,
            },
        )
        decision2 = await self._pipeline.run(ctx2)
        combined = _combine(decision1, decision2)

        if decision2.action in _BLOCKING_ACTIONS:
            proxy_latency_ms = (time.perf_counter() - start) * 1000
            await self._finish_failed_call(
                identity=identity,
                call_id=call_id,
                decision=combined,
                request=request,
                raw_response=assistant_text,
                proxy_latency_ms=proxy_latency_ms,
                upstream_latency_ms=upstream_latency_ms,
                tokens=_tokens_info(response.usage),
            )
            raise self._mapped_error(combined, call_id)

        delivered_text = ctx2.masked_text if ctx2.masked_text is not None else assistant_text
        items_masked = _count_placeholders(ctx1.masked_text) + _count_placeholders(ctx2.masked_text)

        delivered_response = response
        if ctx2.masked_text is not None:
            delivered_choice = response.choices[0].model_copy(
                update={
                    "message": response.choices[0].message.model_copy(
                        update={"content": delivered_text}
                    )
                }
            )
            delivered_response = response.model_copy(update={"choices": [delivered_choice]})

        proxy_latency_ms = (time.perf_counter() - start) * 1000
        stage, rule_id, reason, owasp = _outcome_fields(combined)

        await self._risk_service.record(identity, combined)
        call_record = self._record_builder.build(
            call_id=call_id,
            identity=identity,
            kind=CallKind.chat,
            target="llm.complete",
            status=combined.status,
            provider=self._model_provider.describe(),
            stage=stage,
            rule_id=rule_id,
            reason=reason,
            owasp=owasp,
            request_summary=f"chat: {request.model}",
            request_payload={"model": request.model},
            raw_response=assistant_text,
            delivered_response=delivered_text,
            items_masked=items_masked,
            tokens=_tokens_info(response.usage),
            proxy_latency_ms=proxy_latency_ms,
            upstream_latency_ms=upstream_latency_ms,
            stage_timings=combined.stage_timings_ms,
        )
        await self._audit_service.record(call_record, combined)

        return ChatCompletionOutcome(
            call_id=call_id,
            response=delivered_response,
            status=combined.status,
            stage=stage,
            rule_id=rule_id,
            reason=reason,
            items_masked=items_masked,
            proxy_latency_ms=proxy_latency_ms,
            upstream_latency_ms=upstream_latency_ms,
        )

    async def _finish_failed_call(
        self,
        *,
        identity: Identity,
        call_id: str,
        decision: Decision,
        request: ChatCompletionRequest,
        proxy_latency_ms: float,
        upstream_latency_ms: float,
        raw_response: str | None = None,
        tokens: TokensInfo | None = None,
        error_reason: str | None = None,
    ) -> None:
        if decision.action in _BLOCKING_ACTIONS:
            await self._circuit_breaker.record_block(identity, call_id)
        await self._risk_service.record(identity, decision)

        stage, rule_id, reason, owasp = _outcome_fields(decision)
        reason = reason or error_reason

        call_record = self._record_builder.build(
            call_id=call_id,
            identity=identity,
            kind=CallKind.chat,
            target="llm.complete",
            status=decision.status,
            provider=self._model_provider.describe(),
            stage=stage,
            rule_id=rule_id,
            reason=reason,
            owasp=owasp,
            request_summary=f"chat: {request.model}",
            request_payload={"model": request.model},
            raw_response=raw_response,
            delivered_response=None,
            tokens=tokens or TokensInfo(),
            proxy_latency_ms=proxy_latency_ms,
            upstream_latency_ms=upstream_latency_ms,
            stage_timings=decision.stage_timings_ms,
        )
        await self._audit_service.record(call_record, decision)

    @staticmethod
    def _mapped_error(decision: Decision, call_id: str) -> ControlLayerError:
        resource_block = next(
            (
                r
                for r in decision.stage_results
                if r.stage == StageName.resource and r.action == RuleAction.block
            ),
            None,
        )
        primary = decision.primary_violation
        if resource_block is not None:
            error: ControlLayerError = BudgetExceededError(
                resource_block.reason or "Budget exceeded"
            )
        elif decision.action == RuleAction.quarantine:
            fallback = primary.reason if primary is not None else None
            error = QuarantinedError(fallback or "User is quarantined")
        elif primary is not None and primary.rule_id == "rate_limit":
            error = RateLimitedError(primary.reason or "Rate limit exceeded")
        elif primary is not None:
            error = PolicyViolationError(primary, decision.status)
        else:
            error = QuarantinedError("Request blocked")
        error.call_id = call_id
        return error


def _prompt_turns(request: ChatCompletionRequest) -> list[str]:
    return [m.content or "" for m in request.messages if m.role != "system"]


def _latest_user_text(request: ChatCompletionRequest) -> str:
    for message in reversed(request.messages):
        if message.role == "user":
            return message.content or ""
    return ""


def _apply_masked_prompt(
    request: ChatCompletionRequest, masked_text: str | None
) -> ChatCompletionRequest:
    if masked_text is None:
        return request
    messages = list(request.messages)
    turn_indexes = [i for i, m in enumerate(messages) if m.role != "system"]
    segments = masked_text.split(PROMPT_TURN_SEPARATOR)
    if len(segments) != len(turn_indexes):
        turn_indexes = turn_indexes[-1:]
        segments = [masked_text]
    for index, segment in zip(turn_indexes, segments, strict=False):
        if messages[index].content != segment:
            messages[index] = messages[index].model_copy(update={"content": segment})
    return request.model_copy(update={"messages": messages})


def _append_canary(
    request: ChatCompletionRequest, canary_token: str, policy: PolicyDocument
) -> ChatCompletionRequest:
    canary_enabled = any(r.type == "canary_token" and r.enabled for r in policy.rules)
    if not canary_enabled:
        return request
    messages = list(request.messages)
    for index, message in enumerate(messages):
        if message.role == "system":
            messages[index] = message.model_copy(
                update={"content": f"{message.content or ''}\n{canary_token}"}
            )
            return request.model_copy(update={"messages": messages})
    messages.insert(0, ChatMessage(role="system", content=canary_token))
    return request.model_copy(update={"messages": messages})


def _tokens_info(usage: Usage) -> TokensInfo:
    return TokensInfo(
        prompt=usage.prompt_tokens, completion=usage.completion_tokens, total=usage.total_tokens
    )
