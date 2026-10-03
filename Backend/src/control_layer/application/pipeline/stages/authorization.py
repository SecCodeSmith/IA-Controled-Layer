from __future__ import annotations

from control_layer.application.pipeline.stage_base import BaseStage
from control_layer.application.rules.registry import EvaluatorRegistry
from control_layer.application.rules.rule_runner import RuleFilter, RuleRunner
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import StageResult
from control_layer.domain.models.enums import StageName
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule


def _skip_tool_match_when_approved(ctx: ProcessingContext) -> RuleFilter:
    approved = bool(ctx.metadata.get("approved"))

    def _filter(rule: Rule) -> bool:
        return not (approved and rule.type == "tool_match")

    return _filter


class AuthorizationStage(BaseStage):
    def __init__(self, registry: EvaluatorRegistry) -> None:
        super().__init__(StageName.authorization)
        self._rule_runner = RuleRunner(registry)

    async def process(self, ctx: ProcessingContext, policy: PolicyDocument) -> StageResult:
        rule_filter = _skip_tool_match_when_approved(ctx)
        return await self._rule_runner.run(self.name, ctx, policy, rule_filter=rule_filter)
