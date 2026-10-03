import pytest

from control_layer.application.rules.registry import EvaluatorRegistry
from control_layer.domain.exceptions import UnknownEvaluatorError


class _FakeEvaluator:
    async def evaluate(self, rule, ctx, policy):  # noqa: ANN001
        raise NotImplementedError


def test_register_and_get_round_trips() -> None:
    registry = EvaluatorRegistry()
    evaluator = _FakeEvaluator()
    registry.register("tool_match", evaluator)
    assert registry.get("tool_match") is evaluator


def test_get_unknown_type_raises() -> None:
    registry = EvaluatorRegistry()
    with pytest.raises(UnknownEvaluatorError):
        registry.get("nonsense")


def test_types_lists_registered_types() -> None:
    registry = EvaluatorRegistry()
    registry.register("rbac", _FakeEvaluator())
    registry.register("residency", _FakeEvaluator())
    assert set(registry.types()) == {"rbac", "residency"}


def test_register_overwrites_existing_type() -> None:
    registry = EvaluatorRegistry()
    first = _FakeEvaluator()
    second = _FakeEvaluator()
    registry.register("rbac", first)
    registry.register("rbac", second)
    assert registry.get("rbac") is second
