from __future__ import annotations

import json

import pytest

from control_layer.application.evaluators.authorization.resource_projection import (
    ResourceProjectionEvaluator,
)
from control_layer.domain.models.enums import InterceptionPoint, Role
from control_layer.domain.models.resource import ColumnScope, ResourceConfig, ResourceGrant
from tests.unit.application.evaluators.conftest import (
    make_context,
    make_identity,
    make_policy,
    make_rule,
    make_tool_call,
)

_HR_GRANT = ResourceGrant(columns=ColumnScope(deny=["salary"]), rows={"region": "$identity.region"})
_QUERY = ResourceConfig(
    id="hr_directory_rows", server="hr-db", tools=["query"], records="rows", roles={"hr": _HR_GRANT}
)
_EMPLOYEE = ResourceConfig(
    id="hr_employee_record", server="hr-db", tools=["get_employee"], roles={"hr": _HR_GRANT}
)
_ROWS = {
    "rows": [
        {"id": "E-2001", "region": "PL", "salary": 14200},
        {"id": "E-2101", "region": "DE", "salary": 11800},
    ]
}


def _policy():
    return make_policy().model_copy(update={"resources": [_QUERY, _EMPLOYEE]})


def _rule():
    return make_rule(rule_id="resource_projection", rule_type="resource_projection", action="mask")


def _ctx(text: str, tool: str = "query", role: Role = Role.hr, **kwargs):
    return make_context(
        identity=make_identity(role=role, region="PL"),
        point=kwargs.pop("point", InterceptionPoint.tool_result),
        text=text,
        tool_call=make_tool_call(server="hr-db", tool=tool),
    )


@pytest.mark.asyncio
async def test_rows_and_columns_are_projected() -> None:
    ctx = _ctx(json.dumps(_ROWS))

    outcome = await ResourceProjectionEvaluator().evaluate(_rule(), ctx, _policy())

    assert outcome.matched is True
    assert outcome.reason == "1 row(s) filtered, 1 column(s) redacted: salary"
    assert outcome.evidence == [
        "resource:hr_directory_rows",
        "rows_filtered:1",
        "column_redacted:salary",
    ]
    assert json.loads(outcome.masked_text) == {"rows": [{"id": "E-2001", "region": "PL"}]}


@pytest.mark.asyncio
async def test_reason_omits_column_suffix_when_no_column_was_redacted() -> None:
    data = {"rows": [{"id": "E-2001", "region": "PL"}, {"id": "E-2101", "region": "DE"}]}

    outcome = await ResourceProjectionEvaluator().evaluate(
        _rule(), _ctx(json.dumps(data)), _policy()
    )

    assert outcome.matched is True
    assert outcome.reason == "1 row(s) filtered, 0 column(s) redacted"
    assert outcome.evidence == ["resource:hr_directory_rows", "rows_filtered:1"]


@pytest.mark.asyncio
async def test_unchanged_result_is_not_matched() -> None:
    data = {"rows": [{"id": "E-2001", "region": "PL"}]}

    outcome = await ResourceProjectionEvaluator().evaluate(
        _rule(), _ctx(json.dumps(data)), _policy()
    )

    assert outcome.matched is False
    assert outcome.masked_text is None


@pytest.mark.asyncio
async def test_flat_record_in_scope_without_salary_is_a_no_op() -> None:
    record = {"employee_id": "E-1042", "region": "PL", "pesel": "44051401359"}

    outcome = await ResourceProjectionEvaluator().evaluate(
        _rule(), _ctx(json.dumps(record), tool="get_employee"), _policy()
    )

    assert outcome.matched is False


@pytest.mark.asyncio
async def test_flat_record_outside_row_scope_is_redacted() -> None:
    record = {"employee_id": "E-9", "region": "DE"}

    outcome = await ResourceProjectionEvaluator().evaluate(
        _rule(), _ctx(json.dumps(record), tool="get_employee"), _policy()
    )

    assert outcome.matched is True
    assert json.loads(outcome.masked_text) == {"redacted": "outside row scope"}
    assert outcome.reason == "1 row(s) filtered, 0 column(s) redacted"


@pytest.mark.asyncio
async def test_non_json_result_is_reported_as_unstructured() -> None:
    outcome = await ResourceProjectionEvaluator().evaluate(_rule(), _ctx("plain text"), _policy())

    assert outcome.matched is False
    assert outcome.reason == "unstructured result"


@pytest.mark.asyncio
async def test_role_without_grant_is_not_matched() -> None:
    ctx = _ctx(json.dumps(_ROWS), role=Role.finance)

    outcome = await ResourceProjectionEvaluator().evaluate(_rule(), ctx, _policy())

    assert outcome.matched is False


@pytest.mark.asyncio
async def test_uncovered_tool_is_not_matched() -> None:
    ctx = _ctx(json.dumps(_ROWS), tool="find_approver")

    outcome = await ResourceProjectionEvaluator().evaluate(_rule(), ctx, _policy())

    assert outcome.matched is False


@pytest.mark.asyncio
async def test_non_ascii_text_is_not_escaped() -> None:
    data = {"rows": [{"id": "E-1", "name": "Łukasz", "region": "PL", "salary": 1}]}

    outcome = await ResourceProjectionEvaluator().evaluate(
        _rule(), _ctx(json.dumps(data)), _policy()
    )

    assert "Łukasz" in outcome.masked_text


@pytest.mark.asyncio
async def test_prompt_point_is_ignored() -> None:
    ctx = _ctx(json.dumps(_ROWS), point=InterceptionPoint.prompt)

    outcome = await ResourceProjectionEvaluator().evaluate(_rule(), ctx, _policy())

    assert outcome.matched is False


@pytest.mark.asyncio
async def test_context_without_tool_call_or_identity_is_ignored() -> None:
    evaluator = ResourceProjectionEvaluator()
    without_call = make_context(point=InterceptionPoint.tool_result, text=json.dumps(_ROWS))
    without_identity = make_context(
        point=InterceptionPoint.tool_result,
        text=json.dumps(_ROWS),
        no_identity=True,
        tool_call=make_tool_call(server="hr-db", tool="query"),
    )

    assert (await evaluator.evaluate(_rule(), without_call, _policy())).matched is False
    assert (await evaluator.evaluate(_rule(), without_identity, _policy())).matched is False
