from control_layer.application.evaluators import build_evaluators
from control_layer.application.evaluators.authorization.model_allowlist import (
    ModelAllowlistEvaluator,
)
from control_layer.application.evaluators.behavior.anomaly import AnomalyEvaluator
from control_layer.application.evaluators.dependencies import EvaluatorDependencies
from control_layer.application.evaluators.dlp.canary_token import CanaryTokenEvaluator
from control_layer.application.evaluators.policy.llm_judge import LlmJudgeEvaluator
from control_layer.application.evaluators.policy.ml_classifier import MlClassifierEvaluator
from control_layer.application.evaluators.policy.signatures import SignaturesEvaluator
from tests.unit.application.evaluators.conftest import (
    FakeCacheRepository,
    FakeModelProvider,
    FakePromptClassifier,
    FakeSignatureFeed,
)

EXPECTED_TYPES = {
    "rbac",
    "residency",
    "model_allowlist",
    "tool_match",
    "detectors",
    "sequence",
    "canary_token",
    "signatures",
    "ml_classifier",
    "llm_judge",
    "restricted_topics",
    "unsafe_output",
    "transaction_limit",
    "rate_limit",
    "loop_guard",
    "circuit_breaker",
    "anomaly",
}


def _deps() -> EvaluatorDependencies:
    return EvaluatorDependencies(
        cache=FakeCacheRepository(),
        signature_feed=FakeSignatureFeed([]),
        classifier=FakePromptClassifier(0.0),
        model_provider=FakeModelProvider(content="{}"),
        canary_token="CANARY-1",
        judge_model="qwen2.5:7b",
    )


def test_build_evaluators_returns_every_expected_rule_type() -> None:
    evaluators = build_evaluators(_deps())

    assert set(evaluators.keys()) == EXPECTED_TYPES


def test_build_evaluators_every_entry_is_callable_evaluate() -> None:
    evaluators = build_evaluators(_deps())

    for evaluator in evaluators.values():
        assert callable(evaluator.evaluate)


def test_build_evaluators_wires_dependencies_into_the_right_evaluators() -> None:
    evaluators = build_evaluators(_deps())

    assert isinstance(evaluators["model_allowlist"], ModelAllowlistEvaluator)
    assert isinstance(evaluators["anomaly"], AnomalyEvaluator)
    assert isinstance(evaluators["canary_token"], CanaryTokenEvaluator)
    assert isinstance(evaluators["signatures"], SignaturesEvaluator)
    assert isinstance(evaluators["ml_classifier"], MlClassifierEvaluator)
    assert isinstance(evaluators["llm_judge"], LlmJudgeEvaluator)


def test_build_evaluators_returns_fresh_instances_per_call() -> None:
    deps = _deps()
    first = build_evaluators(deps)
    second = build_evaluators(deps)

    assert first is not second
