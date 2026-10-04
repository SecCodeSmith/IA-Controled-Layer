from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from control_layer.application.evaluators.policy._turn_text import injection_text
from control_layer.domain.models.classifier import CLASSIFIER_TRACE_KEY, TRAINING_SAMPLE_KEY
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import RuleOutcome
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.rule import Rule
from control_layer.domain.models.training_sample import (
    SampleSource,
    SampleStatus,
    TrainingSample,
)
from control_layer.domain.ports.rule_evaluator import RuleEvaluator
from control_layer.domain.ports.training_sample_repository import TrainingSampleRepository

logger = logging.getLogger(__name__)

WORKBENCH_SESSION_PREFIX = "workbench:"


def utcnow() -> datetime:
    return datetime.now(UTC)


class FeedbackRecordingEvaluator:
    def __init__(
        self,
        inner: RuleEvaluator,
        repository: TrainingSampleRepository,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._inner = inner
        self._repository = repository
        self._clock = clock

    async def evaluate(
        self, rule: Rule, ctx: ProcessingContext, policy: PolicyDocument
    ) -> RuleOutcome:
        outcome = await self._inner.evaluate(rule, ctx, policy)
        if not outcome.inconclusive:
            await self._record(outcome, ctx)
        return outcome

    async def _record(self, outcome: RuleOutcome, ctx: ProcessingContext) -> None:
        try:
            stored = await self._repository.add(self._sample(outcome, ctx))
        except Exception:
            logger.exception("failed to record judge verdict as training sample")
            return
        ctx.metadata[TRAINING_SAMPLE_KEY] = stored.id

    def _sample(self, outcome: RuleOutcome, ctx: ProcessingContext) -> TrainingSample:
        trace = ctx.metadata.get(CLASSIFIER_TRACE_KEY)
        return TrainingSample(
            id=uuid4().hex,
            text=injection_text(ctx),
            label=1 if outcome.matched else 0,
            source=_source(ctx.session_id),
            status=SampleStatus.pending,
            confidence=min(max(outcome.confidence, 0.0), 1.0),
            reason=outcome.reason,
            tree_probability=trace.probability if trace is not None else None,
            point=ctx.point,
            call_id=ctx.call_id,
            created_at=self._clock(),
        )


def _source(session_id: str) -> SampleSource:
    if session_id.startswith(WORKBENCH_SESSION_PREFIX):
        return SampleSource.workbench
    return SampleSource.judge
