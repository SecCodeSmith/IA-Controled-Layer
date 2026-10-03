from control_layer.application.evaluators.authorization.residency import ResidencyEvaluator
from control_layer.domain.models.enums import Role
from tests.unit.application.evaluators.conftest import (
    make_context,
    make_descriptor,
    make_identity,
    make_policy,
    make_rule,
)


async def test_no_data_region_is_not_matched() -> None:
    evaluator = ResidencyEvaluator()
    rule = make_rule(rule_type="residency")
    policy = make_policy()
    ctx = make_context(metadata={"tool_descriptor": make_descriptor(data_region=None)})

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_region_within_allowed_regions_is_not_matched() -> None:
    evaluator = ResidencyEvaluator()
    rule = make_rule(rule_type="residency")
    policy = make_policy(locations={"eu_customers": {"allowed_regions": ["PL", "DE"]}})
    ctx = make_context(
        identity=make_identity(role=Role.developer, region="PL"),
        metadata={"tool_descriptor": make_descriptor(data_region="eu_customers")},
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is False


async def test_region_outside_allowed_regions_is_matched() -> None:
    evaluator = ResidencyEvaluator()
    rule = make_rule(rule_type="residency")
    policy = make_policy(locations={"eu_customers": {"allowed_regions": ["PL", "DE"]}})
    ctx = make_context(
        identity=make_identity(role=Role.developer, region="US"),
        metadata={"tool_descriptor": make_descriptor(data_region="eu_customers")},
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
    assert outcome.reason == "Data residency: EU-only"


async def test_unknown_data_region_is_treated_as_no_allowed_regions() -> None:
    evaluator = ResidencyEvaluator()
    rule = make_rule(rule_type="residency")
    policy = make_policy(locations={})
    ctx = make_context(
        identity=make_identity(region="PL"),
        metadata={"tool_descriptor": make_descriptor(data_region="eu_customers")},
    )

    outcome = await evaluator.evaluate(rule, ctx, policy)

    assert outcome.matched is True
