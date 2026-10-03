from __future__ import annotations

from typing import Protocol

from control_layer.domain.models.context import ProcessingContext
from control_layer.domain.models.decision import StageResult
from control_layer.domain.models.enums import StageName
from control_layer.domain.models.policy import PolicyDocument


class PipelineStage(Protocol):
    name: StageName

    async def process(self, ctx: ProcessingContext, policy: PolicyDocument) -> StageResult: ...
