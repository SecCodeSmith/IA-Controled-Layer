from __future__ import annotations

from control_layer.application.pipeline.stage_base import BaseStage
from control_layer.application.rules.registry import EvaluatorRegistry
from control_layer.application.rules.rule_runner import RuleRunner
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import StageResult
from control_layer.domain.models.enums import InterceptionPoint, StageName
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.models.session import SessionState
from control_layer.domain.ports.session_repository import SessionRepository


class BehaviorStage(BaseStage):
    def __init__(self, registry: EvaluatorRegistry, session_repository: SessionRepository) -> None:
        super().__init__(StageName.behavior)
        self._rule_runner = RuleRunner(registry)
        self._session_repository = session_repository

    async def process(self, ctx: ProcessingContext, policy: PolicyDocument) -> StageResult:
        result = await self._rule_runner.run(self.name, ctx, policy)

        session_state = ctx.metadata.get("session_state")
        if session_state is None:
            session_state = SessionState(session_id=ctx.session_id)
            ctx.metadata["session_state"] = session_state

        if ctx.point == InterceptionPoint.tool_result:
            self._apply_taint(ctx, session_state)

        await self._session_repository.save(session_state)
        return result

    @staticmethod
    def _apply_taint(ctx: ProcessingContext, session_state: SessionState) -> None:
        descriptor = ctx.metadata.get("tool_descriptor")
        if descriptor is not None:
            for tag in descriptor.tags:
                if tag not in session_state.tags_seen:
                    session_state.tags_seen.append(tag)

        if ctx.metadata.get("injection_detected"):
            session_state.tainted = True
