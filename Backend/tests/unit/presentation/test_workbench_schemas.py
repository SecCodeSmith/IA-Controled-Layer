from __future__ import annotations

import pytest
from pydantic import ValidationError

from control_layer.domain.models.enums import (
    CallStatus,
    InterceptionPoint,
    RuleAction,
    StageName,
)
from control_layer.domain.models.resource import ResourceGrant
from control_layer.presentation.api.schemas.workbench import (
    JudgeView,
    ResourceMatrixResponse,
    ResourceView,
    StageView,
    ToolCallSpec,
    TraceRequest,
    TraceResponse,
    ViolationView,
)


def test_prompt_trace_request() -> None:
    request = TraceRequest(actor="anna.kowalska", kind="prompt", text="hello")

    assert request.force_verify is False
    assert request.tool_call is None


def test_tool_call_trace_request() -> None:
    request = TraceRequest(
        actor="anna.kowalska",
        kind="tool_call",
        tool_call=ToolCallSpec(server="github", tool="read_file", arguments={"path": ".env"}),
    )

    assert request.tool_call is not None
    assert request.tool_call.arguments == {"path": ".env"}


def test_tool_call_spec_arguments_default_empty() -> None:
    assert ToolCallSpec(server="hr-db", tool="query").arguments == {}


def test_prompt_trace_requires_text() -> None:
    with pytest.raises(ValidationError):
        TraceRequest(actor="anna.kowalska", kind="prompt")


def test_tool_call_trace_requires_tool_call() -> None:
    with pytest.raises(ValidationError):
        TraceRequest(actor="anna.kowalska", kind="tool_call", text="x")


def test_trace_request_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        TraceRequest(actor="anna.kowalska", kind="response", text="x")


def test_trace_response_minimal_shape() -> None:
    response = TraceResponse(
        call_id="CL-1",
        kind="prompt",
        status=CallStatus.ALLOWED,
        action=RuleAction.allow,
    )

    dumped = response.model_dump(mode="json")

    assert set(dumped) == {
        "call_id",
        "kind",
        "status",
        "action",
        "stage",
        "rule_id",
        "reason",
        "masked_text",
        "stages",
        "classifier_trace",
        "judge",
        "training_sample_id",
        "raw_result",
        "delivered_result",
    }
    assert dumped["stages"] == []
    assert dumped["judge"] is None


def test_trace_response_nested_views() -> None:
    stage = StageView(
        stage=StageName.authorization,
        point=InterceptionPoint.tool_result,
        action=RuleAction.mask,
        timing_ms=1.5,
        violations=[
            ViolationView(
                rule_id="resource_projection",
                action=RuleAction.mask,
                reason="1 row(s) filtered",
                evidence=["salary"],
            )
        ],
    )

    response = TraceResponse(
        call_id="CL-2",
        kind="tool_call",
        status=CallStatus.MASKED,
        action=RuleAction.mask,
        stage=StageName.authorization,
        rule_id="resource_projection",
        stages=[stage],
        judge=JudgeView(verdict="allow", confidence=0.8),
        raw_result={"rows": [1, 2]},
        delivered_result={"rows": [1]},
    )

    assert response.stages[0].cache_hit is False
    assert response.stages[0].violations[0].confidence == 1.0
    assert response.judge is not None
    assert response.judge.reason is None


def test_judge_view_rejects_unknown_verdict() -> None:
    with pytest.raises(ValidationError):
        JudgeView(verdict="maybe", confidence=0.5)


def test_resource_matrix_response_shape() -> None:
    response = ResourceMatrixResponse(
        roles=["developer", "hr", "finance"],
        resources=[
            ResourceView(
                id="hr_directory_rows",
                server="hr-db",
                tools=["query"],
                records="rows",
                grants={"hr": ResourceGrant(rows={"region": "$identity.region"})},
            )
        ],
    )

    dumped = response.model_dump(mode="json")

    resource = dumped["resources"][0]
    assert resource["path_argument"] is None
    assert resource["grants"]["hr"]["rows"] == {"region": "$identity.region"}
    assert resource["grants"]["hr"]["columns"] == {"allow": None, "deny": []}
