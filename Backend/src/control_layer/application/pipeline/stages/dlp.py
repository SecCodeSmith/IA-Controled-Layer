from __future__ import annotations

from control_layer.application.pipeline.stage_base import BaseStage
from control_layer.application.rules.registry import EvaluatorRegistry
from control_layer.application.rules.rule_runner import RuleRunner
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import StageResult
from control_layer.domain.models.enums import StageName
from control_layer.domain.models.policy import PolicyDocument


class DlpStage(BaseStage):
    def __init__(self, registry: EvaluatorRegistry) -> None:
        super().__init__(StageName.dlp)
        self._rule_runner = RuleRunner(registry)

    async def process(self, ctx: ProcessingContext, policy: PolicyDocument) -> StageResult:
        return await self._rule_runner.run(self.name, ctx, policy)
