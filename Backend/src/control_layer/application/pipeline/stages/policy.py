from __future__ import annotations

from control_layer.application.pipeline.stage_base import BaseStage
from control_layer.application.rules.registry import EvaluatorRegistry
from control_layer.application.rules.rule_runner import RuleEvaluation, RuleRunner
from control_layer.domain.models.classifier import CLASSIFIER_TRACE_KEY, FORCE_VERIFY_KEY
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome, StageResult
from control_layer.domain.models.enums import RuleAction, StageName
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule

_ESCALATING_RULE_TYPES = {"ml_classifier", "decision_tree"}
_INJECTION_RULE_TYPES = {"signatures", "ml_classifier", "decision_tree", "llm_judge"}
_TERMINAL_ACTIONS = {RuleAction.block, RuleAction.quarantine}
_OVERRULED_REASON = "tree positive overruled by judge"

JUDGE_OUTCOMES_KEY = "judge_outcomes"
JUDGE_VERDICT_KEY = "judge_verdict"


class PolicyStage(BaseStage):
    def __init__(self, registry: EvaluatorRegistry) -> None:
        super().__init__(StageName.policy)
        self._registry = registry
        self._rule_runner = RuleRunner(registry)

    async def process(self, ctx: ProcessingContext, policy: PolicyDocument) -> StageResult:
        evaluations = await self._rule_runner.evaluate_rules(self.name, ctx, policy)
        terminal = _has_terminal_match(evaluations)
        resolved = [
            await self._resolve(evaluation, ctx, policy, terminal=terminal)
            for evaluation in evaluations
        ]
        merged = _merge_repeated_rules(resolved)

        for evaluation in merged:
            if evaluation.outcome.matched and evaluation.rule.type in _INJECTION_RULE_TYPES:
                ctx.metadata["injection_detected"] = True

        return RuleRunner.build_stage_result(self.name, merged)

    async def _resolve(
        self,
        evaluation: RuleEvaluation,
        ctx: ProcessingContext,
        policy: PolicyDocument,
        *,
        terminal: bool,
    ) -> RuleEvaluation:
        rule, outcome = evaluation.rule, evaluation.outcome
        if rule.type not in _ESCALATING_RULE_TYPES or not outcome.inconclusive:
            return evaluation

        if terminal and not ctx.metadata.get(FORCE_VERIFY_KEY):
            settled = outcome.model_copy(update={"inconclusive": False})
            return RuleEvaluation(rule=rule, outcome=settled)

        target_rule = self._enabled_escalation_target(rule, policy)
        if target_rule is None:
            forced = outcome.model_copy(update={"matched": True})
            return RuleEvaluation(
                rule=rule.model_copy(update={"action": RuleAction.flag}), outcome=forced
            )

        judge_outcome = await self._judge(target_rule, ctx, policy)
        if outcome.matched and not judge_outcome.inconclusive and not judge_outcome.matched:
            overruled = outcome.model_copy(
                update={"matched": False, "inconclusive": False, "reason": _OVERRULED_REASON}
            )
            return RuleEvaluation(rule=rule, outcome=overruled)

        evidence = [*judge_outcome.evidence, *_escalation_evidence(rule, ctx)]
        return RuleEvaluation(
            rule=target_rule, outcome=judge_outcome.model_copy(update={"evidence": evidence})
        )

    async def _judge(
        self, target_rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        outcomes: dict[str, RuleOutcome] = ctx.metadata.setdefault(JUDGE_OUTCOMES_KEY, {})
        cached = outcomes.get(target_rule.id)
        if cached is not None:
            return cached

        evaluator = self._registry.get(target_rule.type)
        judge_outcome = await evaluator.evaluate(target_rule, ctx, policy)
        outcomes[target_rule.id] = judge_outcome
        if judge_outcome.masked_text is not None:
            ctx.masked_text = judge_outcome.masked_text
        if not judge_outcome.inconclusive:
            ctx.metadata[JUDGE_VERDICT_KEY] = _verdict_summary(judge_outcome)
        return judge_outcome

    @staticmethod
    def _enabled_escalation_target(rule: Rule, policy: PolicyDocument) -> Rule | None:
        escalate_to = rule.params.get("escalate_to")
        if not escalate_to:
            return None
        for candidate in policy.rules:
            if candidate.id == escalate_to and candidate.enabled:
                return candidate
        return None


def _has_terminal_match(evaluations: list[RuleEvaluation]) -> bool:
    return any(
        evaluation.outcome.matched
        and evaluation.rule.type not in _ESCALATING_RULE_TYPES
        and evaluation.rule.action in _TERMINAL_ACTIONS
        for evaluation in evaluations
    )


def _escalation_evidence(rule: Rule, ctx: ProcessingContext) -> list[str]:
    evidence = [f"escalated_from:{rule.id}"]
    trace = ctx.metadata.get(CLASSIFIER_TRACE_KEY)
    if trace is not None:
        evidence.append(f"tree_p={trace.probability:.2f}")
    return evidence


def _verdict_summary(outcome: RuleOutcome) -> dict[str, object]:
    if not outcome.matched:
        verdict = "allow"
    elif outcome.confidence >= 1.0:
        verdict = "block"
    else:
        verdict = "flag"
    return {"verdict": verdict, "confidence": outcome.confidence, "reason": outcome.reason}


def _merge_repeated_rules(evaluations: list[RuleEvaluation]) -> list[RuleEvaluation]:
    merged: dict[str, RuleEvaluation] = {}
    for evaluation in evaluations:
        existing = merged.get(evaluation.rule.id)
        if existing is None:
            merged[evaluation.rule.id] = evaluation
            continue
        evidence = list(dict.fromkeys([*existing.outcome.evidence, *evaluation.outcome.evidence]))
        merged[evaluation.rule.id] = RuleEvaluation(
            rule=existing.rule, outcome=existing.outcome.model_copy(update={"evidence": evidence})
        )
    return list(merged.values())
