from __future__ import annotations

import hashlib
import json
import re
import time

from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import (
    Decision,
    StageResult,
    Violation,
    merge_action,
    status_for,
)
from control_layer.domain.models.enums import RuleAction, StageName
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.ports.cache_repository import CacheRepository
from control_layer.domain.ports.pipeline_stage import PipelineStage
from control_layer.domain.ports.policy_repository import PolicyRepository

_SHORT_CIRCUIT_ACTIONS = (RuleAction.block, RuleAction.quarantine, RuleAction.require_approval)
_DEFAULT_CACHEABLE_STAGES = frozenset({StageName.dlp, StageName.policy})
_WHITESPACE_RE = re.compile(r"\s+")


class ProcessingPipeline:
    def __init__(
        self,
        stages: list[PipelineStage],
        cache: CacheRepository | None,
        policy_repository: PolicyRepository,
        cacheable_stages: frozenset[StageName] | None = None,
        cache_ttl_s: int = 300,
    ) -> None:
        self._validate_stage_order(stages)
        self._stages = stages
        self._cache = cache
        self._policy_repository = policy_repository
        self._cacheable_stages = (
            cacheable_stages if cacheable_stages is not None else _DEFAULT_CACHEABLE_STAGES
        )
        self._cache_ttl_s = cache_ttl_s

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

    async def run(self, ctx: ProcessingContext) -> Decision:
        policy = await self._policy_repository.current()
        non_audit_stages = [stage for stage in self._stages if stage.name != StageName.audit]
        audit_stage = next((stage for stage in self._stages if stage.name == StageName.audit), None)

        cached_bundle: dict[StageName, StageResult] | None = None
        cache_key: str | None = None
        if self._cache is not None:
            cache_key = self._build_cache_key(ctx, policy)
            raw = await self._cache.get(cache_key)
            if raw is not None:
                cached_bundle = {}
                for item in json.loads(raw):
                    cached_result = StageResult.model_validate(item).model_copy(
                        update={"cache_hit": True}
                    )
                    cached_bundle[cached_result.stage] = cached_result

        stage_results: list[StageResult] = []
        violations: list[Violation] = []
        actions: list[RuleAction] = []
        stage_timings: dict[str, float] = {}
        newly_computed_cacheable: list[StageResult] = []

        for stage in non_audit_stages:
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

            stage_results.append(result)
            stage_timings[stage.name.value] = result.timing_ms
            actions.append(result.action)
            violations.extend(result.violations)
            if result.masked_text is not None:
                ctx.masked_text = result.masked_text

            if result.action in _SHORT_CIRCUIT_ACTIONS:
                break

        should_populate_cache = (
            self._cache is not None
            and cached_bundle is None
            and newly_computed_cacheable
            and cache_key is not None
        )
        if should_populate_cache:
            payload = json.dumps(
                [result.model_dump(mode="json") for result in newly_computed_cacheable]
            )
            await self._cache.set(cache_key, payload, ttl=self._cache_ttl_s)

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
