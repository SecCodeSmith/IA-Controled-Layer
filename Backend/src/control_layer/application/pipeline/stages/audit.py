from __future__ import annotations

from control_layer.application.pipeline.stage_base import BaseStage
from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import StageResult
from control_layer.domain.models.enums import StageName
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.ports.event_publisher import EventPublisher


class AuditStage(BaseStage):
    def __init__(self, event_publisher: EventPublisher) -> None:
        super().__init__(StageName.audit)
        self._event_publisher = event_publisher

    async def process(self, ctx: ProcessingContext, policy: PolicyDocument) -> StageResult:
        await self._event_publisher.publish(
            "stage_trace",
            {
                "call_id": ctx.call_id,
                "point": ctx.point.value,
                "stages": ctx.metadata.get("stage_timings", {}),
            },
        )
        return self.allow(0.0)
