from __future__ import annotations

import hashlib
import json
import re
import time

from control_layer.application.services.protection_service import ProtectionService
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import (
    Decision,
    StageResult,
    Violation,
    merge_action,
    status_for,
)
from control_layer.domain.models.enums import ProtectionMode, RuleAction, StageName
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.ports.cache_repository import CacheRepository
from control_layer.domain.ports.pipeline_stage import PipelineStage
from control_layer.domain.ports.policy_repository import PolicyRepository

_SHORT_CIRCUIT_ACTIONS = (RuleAction.block, RuleAction.quarantine, RuleAction.require_approval)
_DEFAULT_CACHEABLE_STAGES = frozenset({StageName.dlp, StageName.policy})
_WHITESPACE_RE = re.compile(r"\s+")
_DOWNGRADED_ACTIONS = frozenset(
    {RuleAction.block, RuleAction.quarantine, RuleAction.require_approval, RuleAction.mask}
)
_MONITOR_PREFIX = "[monitor] "
_OFF_MODE_STAGES = frozenset({StageName.identity, StageName.audit})


def _monitor_reason(reason: str | None) -> str | None:
    return None if reason is None else f"{_MONITOR_PREFIX}{reason}"


def _downgrade_violation(violation: Violation) -> Violation:
    if violation.action not in _DOWNGRADED_ACTIONS:
        return violation
    return violation.model_copy(
        update={"action": RuleAction.flag, "reason": _monitor_reason(violation.reason)}
    )


def _downgrade_result(result: StageResult) -> StageResult:
    if result.action not in _DOWNGRADED_ACTIONS and not result.violations:
        return result
    downgraded = result.action in _DOWNGRADED_ACTIONS
    return result.model_copy(
        update={
            "action": RuleAction.flag if downgraded else result.action,
            "violations": [_downgrade_violation(v) for v in result.violations],
            "masked_text": None if downgraded else result.masked_text,
            "approval_id": None if downgraded else result.approval_id,
            "reason": _monitor_reason(result.reason) if downgraded else result.reason,
        }
    )


class ProcessingPipeline:
    def __init__(
        self,
        stages: list[PipelineStage],
        cache: CacheRepository | None,
        policy_repository: PolicyRepository,
        cacheable_stages: frozenset[StageName] | None = None,
        cache_ttl_s: int = 300,
        protection: ProtectionService | None = None,
    ) -> None:
        self._validate_stage_order(stages)
        self._stages = stages
        self._cache = cache
        self._policy_repository = policy_repository
        self._cacheable_stages = (
            cacheable_stages if cacheable_stages is not None else _DEFAULT_CACHEABLE_STAGES
        )
        self._cache_ttl_s = cache_ttl_s
        self._protection = protection

    @staticmethod
    def _validate_stage_order(stages: list[PipelineStage]) -> None:
        names = [stage.name for stage in stages]
        if len(set(names)) != len(names):
            raise ValueError(
                f"pipeline stages must have unique names, got {[n.value for n in names]}"
            )
        order_index = {name: index for index, name in enumerate(StageName.ordered())}
        indices = [order_index[name] for name in names]
        if indices != sorted(indices):
            raise ValueError(
                "pipeline stages must be registered in StageName.ordered() order, "
                f"got {[n.value for n in names]}"
            )

    @staticmethod
    def _build_cache_key(ctx: ProcessingContext, policy: PolicyDocument) -> str:
        role = ctx.identity.role.value if ctx.identity is not None else "anonymous"
        point = ctx.point.value
        normalized = _WHITESPACE_RE.sub(" ", ctx.current_text.strip().lower())
        digest = hashlib.sha256(f"{role}|{point}|{normalized}".encode()).hexdigest()
        return f"decision:{policy.version}:{digest}"

    @staticmethod
    async def _load_bundle(
        cache: CacheRepository, cache_key: str
    ) -> dict[StageName, StageResult] | None:
        raw = await cache.get(cache_key)
        if raw is None:
            return None
        bundle: dict[StageName, StageResult] = {}
        for item in json.loads(raw):
            cached_result = StageResult.model_validate(item).model_copy(update={"cache_hit": True})
            bundle[cached_result.stage] = cached_result
        return bundle

    async def run(self, ctx: ProcessingContext) -> Decision:
        policy = await self._policy_repository.current()
        mode = await self._protection.get_mode() if self._protection else ProtectionMode.enforce
        is_off = mode is ProtectionMode.off
        non_audit_stages = [
            stage
            for stage in self._stages
            if stage.name != StageName.audit and (not is_off or stage.name in _OFF_MODE_STAGES)
        ]
        cache = None if is_off else self._cache
        audit_stage = next((stage for stage in self._stages if stage.name == StageName.audit), None)

        cached_bundle: dict[StageName, StageResult] | None = None
        cache_key: str | None = None

        stage_results: list[StageResult] = []
        violations: list[Violation] = []
        actions: list[RuleAction] = []
        stage_timings: dict[str, float] = {}
        newly_computed_cacheable: list[StageResult] = []

        for stage in non_audit_stages:
            if cache is not None and cache_key is None and stage.name in self._cacheable_stages:
                cache_key = self._build_cache_key(ctx, policy)
                cached_bundle = await self._load_bundle(cache, cache_key)
            is_cacheable_hit = (
                cached_bundle is not None
                and stage.name in self._cacheable_stages
                and stage.name in cached_bundle
            )
            if is_cacheable_hit:
                result = cached_bundle[stage.name]
            else:
                start = time.perf_counter()
                result = await stage.process(ctx, policy)
                elapsed_ms = (time.perf_counter() - start) * 1000
                result = result.model_copy(update={"timing_ms": elapsed_ms})
                if stage.name in self._cacheable_stages:
                    newly_computed_cacheable.append(result)

            if mode is ProtectionMode.monitor:
                result = _downgrade_result(result)

            stage_results.append(result)
            stage_timings[stage.name.value] = result.timing_ms
            actions.append(result.action)
            violations.extend(result.violations)
            if result.masked_text is not None:
                ctx.masked_text = result.masked_text

            if result.action in _SHORT_CIRCUIT_ACTIONS:
                break

        should_populate_cache = (
            cache is not None
            and cached_bundle is None
            and newly_computed_cacheable
            and cache_key is not None
        )
        if should_populate_cache:
            payload = json.dumps(
                [result.model_dump(mode="json") for result in newly_computed_cacheable]
            )
            await cache.set(cache_key, payload, ttl=self._cache_ttl_s)

        if audit_stage is not None:
            start = time.perf_counter()
            audit_result = await audit_stage.process(ctx, policy)
            elapsed_ms = (time.perf_counter() - start) * 1000
            audit_result = audit_result.model_copy(update={"timing_ms": elapsed_ms})
            stage_results.append(audit_result)
            stage_timings[audit_stage.name.value] = audit_result.timing_ms
            actions.append(audit_result.action)
            violations.extend(audit_result.violations)

        final_action = merge_action(actions)
        approval_id = next(
            (
                result.approval_id
                for result in reversed(stage_results)
                if result.approval_id is not None
            ),
            None,
        )

        return Decision(
            status=status_for(final_action),
            action=final_action,
            violations=violations,
            masked_text=ctx.masked_text,
            approval_id=approval_id,
            stage_results=stage_results,
            stage_timings_ms=stage_timings,
        )
