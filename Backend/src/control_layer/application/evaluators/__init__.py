from __future__ import annotations

from control_layer.application.evaluators.authorization.model_allowlist import (
    ModelAllowlistEvaluator,
)
from control_layer.application.evaluators.authorization.rbac import RbacEvaluator
from control_layer.application.evaluators.authorization.residency import ResidencyEvaluator
from control_layer.application.evaluators.authorization.resource_projection import (
    ResourceProjectionEvaluator,
)
from control_layer.application.evaluators.authorization.resource_scope import (
    ResourceScopeEvaluator,
)
from control_layer.application.evaluators.authorization.tool_match import ToolMatchEvaluator
from control_layer.application.evaluators.behavior.anomaly import AnomalyEvaluator
from control_layer.application.evaluators.behavior.circuit_breaker import CircuitBreakerEvaluator
from control_layer.application.evaluators.behavior.loop_guard import LoopGuardEvaluator
from control_layer.application.evaluators.behavior.rate_limit import RateLimitEvaluator
from control_layer.application.evaluators.dependencies import EvaluatorDependencies
from control_layer.application.evaluators.dlp.canary_token import CanaryTokenEvaluator
from control_layer.application.evaluators.dlp.detectors import DetectorsEvaluator
from control_layer.application.evaluators.dlp.sequence import SequenceEvaluator
from control_layer.application.evaluators.policy.decision_tree import DecisionTreeEvaluator
from control_layer.application.evaluators.policy.llm_judge import LlmJudgeEvaluator
from control_layer.application.evaluators.policy.ml_classifier import MlClassifierEvaluator
from control_layer.application.evaluators.policy.restricted_topics import (
    RestrictedTopicsEvaluator,
)
from control_layer.application.evaluators.policy.signatures import SignaturesEvaluator
from control_layer.application.evaluators.policy.transaction_limit import (
    TransactionLimitEvaluator,
)
from control_layer.application.evaluators.policy.unsafe_output import UnsafeOutputEvaluator
from control_layer.domain.ports.rule_evaluator import RuleEvaluator


def build_evaluators(deps: EvaluatorDependencies) -> dict[str, RuleEvaluator]:
    return {
        "rbac": RbacEvaluator(),
        "residency": ResidencyEvaluator(),
        "model_allowlist": ModelAllowlistEvaluator(),
        "resource_scope": ResourceScopeEvaluator(),
        "resource_projection": ResourceProjectionEvaluator(),
        "tool_match": ToolMatchEvaluator(),
        "detectors": DetectorsEvaluator(),
        "sequence": SequenceEvaluator(),
        "canary_token": CanaryTokenEvaluator(deps.canary_token),
        "signatures": SignaturesEvaluator(deps.signature_feed),
        "decision_tree": DecisionTreeEvaluator(deps.tree_classifier, deps.sampler),
        "ml_classifier": MlClassifierEvaluator(deps.classifier),
        "llm_judge": LlmJudgeEvaluator(deps.model_provider, deps.judge_model),
        "restricted_topics": RestrictedTopicsEvaluator(),
        "unsafe_output": UnsafeOutputEvaluator(),
        "transaction_limit": TransactionLimitEvaluator(),
        "rate_limit": RateLimitEvaluator(deps.cache),
        "loop_guard": LoopGuardEvaluator(deps.cache),
        "circuit_breaker": CircuitBreakerEvaluator(deps.cache),
        "anomaly": AnomalyEvaluator(deps.cache),
    }
