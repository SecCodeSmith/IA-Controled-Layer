from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from control_layer.application.gateway.ollama_mapping import (
    GatewayReply,
    blocked_reply,
    control_layer_extension,
    ms_to_ns,
    reply_from_response,
    upstream_error_reply,
)
from control_layer.domain.exceptions import ControlLayerError
from control_layer.domain.models.chat import ChatCompletionRequest
from control_layer.presentation.api.error_handlers import describe_error
from control_layer.presentation.composition_root import Container

_IN_BAND_CODES = frozenset(
    {"policy_violation", "quarantined", "rate_limited", "budget_exceeded", "upstream_error"}
)


@dataclass(frozen=True)
class GatewayResult:
    reply: GatewayReply
    control_layer: dict[str, Any]
    total_ns: int
    eval_ns: int


async def run_gateway_chat(
    container: Container, token: str, session: str, request: ChatCompletionRequest
) -> GatewayResult:
    start = time.perf_counter()
    try:
        outcome = await container.chat_completion.execute(token, session, request)
    except ControlLayerError as exc:
        fields = describe_error(exc)
        if fields is None or fields.code not in _IN_BAND_CODES:
            raise
        elapsed = ms_to_ns((time.perf_counter() - start) * 1000)
        stage = fields.stage.value if fields.stage else None
        reply = (
            upstream_error_reply(fields.reason)
            if fields.code == "upstream_error"
            else blocked_reply(stage, fields.rule_id, fields.reason)
        )
        return GatewayResult(
            reply=reply,
            control_layer={
                "call_id": fields.call_id,
                "status": fields.status.value,
                "stage": stage,
                "rule_id": fields.rule_id,
                "reason": fields.reason,
                "items_masked": 0,
                "proxy_latency_ms": elapsed / 1_000_000,
                "upstream_latency_ms": 0.0,
            },
            total_ns=elapsed,
            eval_ns=0,
        )
    return GatewayResult(
        reply=reply_from_response(outcome.response),
        control_layer=control_layer_extension(outcome),
        total_ns=ms_to_ns(outcome.proxy_latency_ms),
        eval_ns=ms_to_ns(outcome.upstream_latency_ms),
    )
