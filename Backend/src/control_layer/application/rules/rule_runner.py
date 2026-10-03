from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from control_layer.application.rules.registry import EvaluatorRegistry
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import (
    RuleOutcome,
    StageResult,
    Violation,
    merge_action,
    pick_primary_violation,
)
from control_layer.domain.models.enums import StageName
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule

RuleFilter = Callable[[Rule], bool]


@dataclass(frozen=True)
class RuleEvaluation:
    rule: Rule
    outcome: RuleOutcome


class RuleRunner:
    def __init__(self, registry: EvaluatorRegistry) -> None:
        self._registry = registry

    def applicable_rules(
        self,
        stage: StageName,
        ctx: ProcessingContext,
        policy: PolicyDocument,
        rule_filter: RuleFilter | None = None,
    ) -> list[Rule]:
        return [
            rule
            for rule in policy.rules
            if rule.enabled
            and rule.stage == stage
            and ctx.point in rule.on
            and (rule_filter is None or rule_filter(rule))
        ]

    async def evaluate_rules(
        self,
        stage: StageName,
        ctx: ProcessingContext,
        policy: PolicyDocument,
        rule_filter: RuleFilter | None = None,
    ) -> list[RuleEvaluation]:
        evaluations: list[RuleEvaluation] = []
        for rule in self.applicable_rules(stage, ctx, policy, rule_filter):
            evaluator = self._registry.get(rule.type)
            outcome = await evaluator.evaluate(rule, ctx, policy)
            if outcome.masked_text is not None:
                ctx.masked_text = outcome.masked_text
            evaluations.append(RuleEvaluation(rule=rule, outcome=outcome))
        return evaluations

    @staticmethod
    def build_stage_result(stage: StageName, evaluations: list[RuleEvaluation]) -> StageResult:
        violations: list[Violation] = []
        masked_text: str | None = None
        for evaluation in evaluations:
            if evaluation.outcome.masked_text is not None:
                masked_text = evaluation.outcome.masked_text
            if evaluation.outcome.matched:
                violations.append(
                    Violation(
                        stage=stage,
                        rule_id=evaluation.rule.id,
                        action=evaluation.rule.action,
                        severity=evaluation.rule.severity,
                        owasp=evaluation.rule.owasp,
                        evidence=evaluation.outcome.evidence,
                        confidence=evaluation.outcome.confidence,
                        reason=evaluation.outcome.reason,
                    )
                )
        action = merge_action([violation.action for violation in violations])
        primary = pick_primary_violation(violations)
        return StageResult(
            stage=stage,
            action=action,
            violations=violations,
            masked_text=masked_text,
            timing_ms=0.0,
            reason=primary.reason if primary else None,
        )

    async def run(
        self,
        stage: StageName,
        ctx: ProcessingContext,
        policy: PolicyDocument,
        rule_filter: RuleFilter | None = None,
    ) -> StageResult:
        evaluations = await self.evaluate_rules(stage, ctx, policy, rule_filter)
        return self.build_stage_result(stage, evaluations)
