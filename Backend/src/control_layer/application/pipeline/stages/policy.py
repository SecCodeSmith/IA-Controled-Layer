from __future__ import annotations

from control_layer.application.pipeline.stage_base import BaseStage
from control_layer.application.rules.registry import EvaluatorRegistry
from control_layer.application.rules.rule_runner import RuleEvaluation, RuleRunner
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import StageResult
from control_layer.domain.models.enums import RuleAction, StageName
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule

_INJECTION_RULE_TYPES = {"signatures", "ml_classifier", "llm_judge"}


class PolicyStage(BaseStage):
    def __init__(self, registry: EvaluatorRegistry) -> None:
        super().__init__(StageName.policy)
        self._registry = registry
        self._rule_runner = RuleRunner(registry)

    async def process(self, ctx: ProcessingContext, policy: PolicyDocument) -> StageResult:
        evaluations = await self._rule_runner.evaluate_rules(self.name, ctx, policy)
        resolved = [await self._resolve(evaluation, ctx, policy) for evaluation in evaluations]

        for evaluation in resolved:
            if evaluation.outcome.matched and evaluation.rule.type in _INJECTION_RULE_TYPES:
                ctx.metadata["injection_detected"] = True

        return RuleRunner.build_stage_result(self.name, resolved)

    async def _resolve(
        self, evaluation: RuleEvaluation, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleEvaluation:
        rule, outcome = evaluation.rule, evaluation.outcome
        if rule.type != "ml_classifier" or not outcome.inconclusive:
            return evaluation

        target_rule = self._enabled_escalation_target(rule, policy)
        if target_rule is None:
            forced = outcome.model_copy(update={"matched": True})
            return RuleEvaluation(
                rule=rule.model_copy(update={"action": RuleAction.flag}), outcome=forced
            )

        evaluator = self._registry.get(target_rule.type)
        judge_outcome = await evaluator.evaluate(target_rule, ctx, policy)
        if judge_outcome.masked_text is not None:
            ctx.masked_text = judge_outcome.masked_text
        return RuleEvaluation(rule=target_rule, outcome=judge_outcome)

    @staticmethod
    def _enabled_escalation_target(rule: Rule, policy: PolicyDocument) -> Rule | None:
        escalate_to = rule.params.get("escalate_to")
        if not escalate_to:
            return None
        for candidate in policy.rules:
            if candidate.id == escalate_to and candidate.enabled:
                return candidate
        return None
