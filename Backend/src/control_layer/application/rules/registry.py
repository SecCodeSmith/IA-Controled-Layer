from __future__ import annotations

from control_layer.domain.exceptions import UnknownEvaluatorError
from control_layer.domain.ports.rule_evaluator import RuleEvaluator


class EvaluatorRegistry:
    def __init__(self) -> None:
        self._evaluators: dict[str, RuleEvaluator] = {}

    def register(self, rule_type: str, evaluator: RuleEvaluator) -> None:
        self._evaluators[rule_type] = evaluator

    def get(self, rule_type: str) -> RuleEvaluator:
        try:
            return self._evaluators[rule_type]
        except KeyError:
            raise UnknownEvaluatorError(rule_type) from None

    def types(self) -> list[str]:
        return list(self._evaluators.keys())
