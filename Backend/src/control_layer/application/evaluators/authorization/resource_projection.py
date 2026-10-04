from __future__ import annotations

import json

from control_layer.application.resources.projection import project_result
from control_layer.application.resources.resolver import find_grant
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.enums import InterceptionPoint
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.resource import ProjectionResult
from control_layer.domain.models.rule import Rule


def _reason(result: ProjectionResult) -> str:
    columns = result.columns_redacted
    summary = f"{result.rows_filtered} row(s) filtered, {len(columns)} column(s) redacted"
    return f"{summary}: {', '.join(columns)}" if columns else summary


def _evidence(resource_id: str, result: ProjectionResult) -> list[str]:
    evidence = [f"resource:{resource_id}", f"rows_filtered:{result.rows_filtered}"]
    evidence.extend(f"column_redacted:{column}" for column in result.columns_redacted)
    return evidence


class ResourceProjectionEvaluator:
    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        if (
            ctx.point is not InterceptionPoint.tool_result
            or ctx.tool_call is None
            or ctx.identity is None
        ):
            return RuleOutcome(matched=False)

        try:
            data = json.loads(ctx.current_text)
        except ValueError:
            return RuleOutcome(matched=False, reason="unstructured result")

        call = ctx.tool_call
        match = find_grant(policy, call.server, call.tool, ctx.identity.role.value)
        if match is None or match.grant is None:
            return RuleOutcome(matched=False)

        result = project_result(data, match.resource, match.grant, ctx.identity)
        if not result.changed:
            return RuleOutcome(matched=False)
        return RuleOutcome(
            matched=True,
            masked_text=json.dumps(result.data, ensure_ascii=False),
            reason=_reason(result),
            evidence=_evidence(match.resource.id, result),
        )
