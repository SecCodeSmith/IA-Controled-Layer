from __future__ import annotations

import pytest

from control_layer.application.pipeline.processing_pipeline import ProcessingPipeline
from control_layer.application.services.protection_service import ProtectionService
from control_layer.domain.exceptions import IdentityRejectedError
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import StageResult, Violation
from control_layer.domain.models.enums import (
    CallStatus,
    InterceptionPoint,
    ProtectionMode,
    RuleAction,
    Severity,
    StageName,
)
from control_layer.infrastructure.cache.in_memory_cache_repository import InMemoryCacheRepository
from tests.unit.application.test_processing_pipeline import FakePolicyRepository, _ctx, _policy


class _Stage:
    def __init__(self, name: StageName, calls: list[StageName], result: StageResult) -> None:
        self.name = name
        self._calls = calls
        self._result = result

    async def process(self, ctx: ProcessingContext, policy: object) -> StageResult:
        self._calls.append(self.name)
        return self._result


class _RejectingIdentityStage:
    name = StageName.identity

    async def process(self, ctx: ProcessingContext, policy: object) -> StageResult:
        raise IdentityRejectedError("bad token")


def _violation(stage: StageName, rule_id: str, action: RuleAction) -> Violation:
    return Violation(
        stage=stage,
        rule_id=rule_id,
        action=action,
        severity=Severity.high,
        reason="denied",
    )


def _result(
    stage: StageName,
    action: RuleAction = RuleAction.allow,
    violations: list[Violation] | None = None,
    masked_text: str | None = None,
    approval_id: str | None = None,
) -> StageResult:
    return StageResult(
        stage=stage,
        action=action,
        violations=violations or [],
        masked_text=masked_text,
        approval_id=approval_id,
        timing_ms=0.0,
        reason="denied" if action is not RuleAction.allow else None,
    )


def _blocked(stage: StageName, rule_id: str) -> StageResult:
    return _result(stage, RuleAction.block, [_violation(stage, rule_id, RuleAction.block)])


def _pipeline(
    stages: list[object], protection: ProtectionService, cache: InMemoryCacheRepository
) -> ProcessingPipeline:
    return ProcessingPipeline(
        stages=stages,  # type: ignore[arg-type]
        cache=cache,
        policy_repository=FakePolicyRepository(_policy()),
        protection=protection,
    )


def _stages(calls: list[StageName], **overrides: StageResult) -> list[object]:
    return [
        _Stage(name, calls, overrides.get(name.value, _result(name)))
        for name in StageName.ordered()
    ]


async def _setup(mode: ProtectionMode) -> tuple[ProtectionService, InMemoryCacheRepository]:
    cache = InMemoryCacheRepository()
    protection = ProtectionService(cache)
    await protection.set_mode(mode)
    return protection, cache


async def test_enforce_mode_keeps_blocking_and_short_circuits() -> None:
    protection, cache = await _setup(ProtectionMode.enforce)
    calls: list[StageName] = []
    stages = _stages(calls, authorization=_blocked(StageName.authorization, "role_provisioning"))

    decision = await _pipeline(stages, protection, cache).run(_ctx())

    assert decision.status is CallStatus.BLOCKED
    assert StageName.dlp not in calls


async def test_monitor_downgrades_block_to_flag_and_keeps_rule_and_stage() -> None:
    protection, cache = await _setup(ProtectionMode.monitor)
    calls: list[StageName] = []
    stages = _stages(calls, authorization=_blocked(StageName.authorization, "role_provisioning"))

    decision = await _pipeline(stages, protection, cache).run(_ctx())

    assert decision.status is CallStatus.FLAGGED
    assert decision.action is RuleAction.flag
    assert calls == StageName.ordered()
    violation = decision.primary_violation
    assert violation is not None
    assert (violation.rule_id, violation.stage) == ("role_provisioning", StageName.authorization)
    assert violation.action is RuleAction.flag
    assert violation.reason == "[monitor] denied"


async def test_monitor_leaves_text_unmasked_and_drops_approval() -> None:
    protection, cache = await _setup(ProtectionMode.monitor)
    masked = _result(
        StageName.dlp,
        RuleAction.mask,
        [_violation(StageName.dlp, "pii_masking", RuleAction.mask)],
        masked_text="[EMAIL]",
    )
    approval = _result(
        StageName.policy,
        RuleAction.require_approval,
        [_violation(StageName.policy, "needs_approval", RuleAction.require_approval)],
        approval_id="ap_1",
    )

    decision = await _pipeline(
        _stages([], dlp=masked, policy=approval), protection, cache
    ).run(_ctx("raw text"))

    assert decision.status is CallStatus.FLAGGED
    assert decision.masked_text is None
    assert decision.approval_id is None
    assert {v.rule_id for v in decision.violations} == {"pii_masking", "needs_approval"}


async def test_monitor_does_not_poison_the_decision_cache_with_downgraded_results() -> None:
    protection, cache = await _setup(ProtectionMode.monitor)
    pipeline = _pipeline(_stages([], dlp=_blocked(StageName.dlp, "pii_masking")), protection, cache)
    await pipeline.run(_ctx("same text"))

    await protection.set_mode(ProtectionMode.enforce)
    decision = await pipeline.run(_ctx("same text"))

    assert decision.status is CallStatus.BLOCKED


async def test_off_mode_runs_only_identity_and_audit_and_allows() -> None:
    protection, cache = await _setup(ProtectionMode.off)
    calls: list[StageName] = []
    stages = _stages(calls, authorization=_blocked(StageName.authorization, "role_provisioning"))

    decision = await _pipeline(stages, protection, cache).run(_ctx())

    assert calls == [StageName.identity, StageName.audit]
    assert decision.status is CallStatus.ALLOWED
    assert decision.violations == []
    assert set(decision.stage_timings_ms) == {"identity", "audit"}


async def test_off_mode_still_runs_identity_and_raises_on_failure() -> None:
    protection, cache = await _setup(ProtectionMode.off)
    stages = [_RejectingIdentityStage(), _Stage(StageName.audit, [], _result(StageName.audit))]

    with pytest.raises(IdentityRejectedError):
        await _pipeline(stages, protection, cache).run(_ctx(point=InterceptionPoint.tool_call))


async def test_pipeline_without_protection_behaves_as_enforce() -> None:
    calls: list[StageName] = []
    pipeline = ProcessingPipeline(
        stages=_stages(  # type: ignore[arg-type]
            calls, authorization=_blocked(StageName.authorization, "role_provisioning")
        ),
        cache=None,
        policy_repository=FakePolicyRepository(_policy()),
    )

    assert (await pipeline.run(_ctx())).status is CallStatus.BLOCKED
