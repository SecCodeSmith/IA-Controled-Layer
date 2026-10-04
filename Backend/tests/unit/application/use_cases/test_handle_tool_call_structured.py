from __future__ import annotations

import pytest

from control_layer.domain.exceptions import PolicyViolationError
from control_layer.domain.models.decision import Decision
from control_layer.domain.models.enums import CallStatus, RuleAction, StageName
from control_layer.domain.models.tool import ToolCallResult
from tests.unit.application.use_cases.test_handle_tool_call import (
    _build_use_case,
    _FakeMcpGateway,
    _identity,
    _request,
    _ScriptedPipeline,
    _violation,
)

pytestmark = pytest.mark.asyncio

_ALLOWED = Decision(status=CallStatus.ALLOWED, action=RuleAction.allow)
_MASKED = Decision(
    status=CallStatus.MASKED,
    action=RuleAction.mask,
    violations=[_violation(RuleAction.mask, "resource_projection", StageName.authorization)],
)
_RAW_STRUCTURED = {"rows": [{"id": "E-2001", "salary": 14200}, {"id": "E-2101", "salary": 11800}]}


def _gateway() -> _FakeMcpGateway:
    return _FakeMcpGateway(
        ToolCallResult(
            content_text='{"rows": []}',
            structured_content=_RAW_STRUCTURED,
        )
    )


async def test_masked_json_object_replaces_structured_content() -> None:
    pipeline = _ScriptedPipeline(
        [(_ALLOWED, None), (_MASKED, '{"rows": [{"id": "E-2001"}]}')], _identity()
    )

    outcome = await _build_use_case(pipeline, mcp_gateway=_gateway()).execute(
        "token", "s1", _request()
    )

    assert outcome.result.content_text == '{"rows": [{"id": "E-2001"}]}'
    assert outcome.result.structured_content == {"rows": [{"id": "E-2001"}]}


async def test_masked_text_that_is_not_json_clears_structured_content() -> None:
    pipeline = _ScriptedPipeline([(_ALLOWED, None), (_MASKED, "[EMAIL_1] seen")], _identity())

    outcome = await _build_use_case(pipeline, mcp_gateway=_gateway()).execute(
        "token", "s1", _request()
    )

    assert outcome.result.structured_content is None


async def test_masked_json_that_is_not_an_object_clears_structured_content() -> None:
    pipeline = _ScriptedPipeline([(_ALLOWED, None), (_MASKED, "[1, 2]")], _identity())

    outcome = await _build_use_case(pipeline, mcp_gateway=_gateway()).execute(
        "token", "s1", _request()
    )

    assert outcome.result.structured_content is None


async def test_unmasked_result_keeps_original_structured_content() -> None:
    pipeline = _ScriptedPipeline([(_ALLOWED, None), (_ALLOWED, None)], _identity())

    outcome = await _build_use_case(pipeline, mcp_gateway=_gateway()).execute(
        "token", "s1", _request()
    )

    assert outcome.result.structured_content == _RAW_STRUCTURED


async def test_success_outcome_carries_the_combined_decision() -> None:
    pipeline = _ScriptedPipeline([(_ALLOWED, None), (_MASKED, '{"rows": []}')], _identity())

    outcome = await _build_use_case(pipeline, mcp_gateway=_gateway()).execute(
        "token", "s1", _request()
    )

    assert outcome.decision is not None
    assert outcome.decision.status is CallStatus.MASKED
    assert [v.rule_id for v in outcome.decision.violations] == ["resource_projection"]


async def test_escalated_outcome_carries_the_first_pass_decision() -> None:
    escalation = Decision(
        status=CallStatus.ESCALATED,
        action=RuleAction.require_approval,
        violations=[
            _violation(
                RuleAction.require_approval,
                "destructive_requires_approval",
                StageName.authorization,
            )
        ],
    )
    pipeline = _ScriptedPipeline([(escalation, None)], _identity())

    outcome = await _build_use_case(pipeline).execute("token", "s1", _request())

    assert outcome.status is CallStatus.ESCALATED
    assert outcome.decision is escalation


async def test_blocked_error_exposes_the_decision() -> None:
    blocked = Decision(
        status=CallStatus.BLOCKED,
        action=RuleAction.block,
        violations=[_violation(RuleAction.block, "resource_scope", StageName.authorization)],
    )
    pipeline = _ScriptedPipeline([(blocked, None)], _identity())

    with pytest.raises(PolicyViolationError) as raised:
        await _build_use_case(pipeline).execute("token", "s1", _request())

    assert raised.value.decision is blocked


async def test_result_stage_block_error_exposes_the_combined_decision() -> None:
    blocked_result = Decision(
        status=CallStatus.BLOCKED,
        action=RuleAction.block,
        violations=[_violation(RuleAction.block, "indirect_injection", StageName.policy)],
    )
    pipeline = _ScriptedPipeline([(_ALLOWED, None), (blocked_result, None)], _identity())

    with pytest.raises(PolicyViolationError) as raised:
        await _build_use_case(pipeline, mcp_gateway=_gateway()).execute("token", "s1", _request())

    assert raised.value.decision.status is CallStatus.BLOCKED
    assert [v.rule_id for v in raised.value.decision.violations] == ["indirect_injection"]
