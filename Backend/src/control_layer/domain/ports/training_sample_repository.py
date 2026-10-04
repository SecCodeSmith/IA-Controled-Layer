from __future__ import annotations

import builtins
from typing import Protocol

from control_layer.domain.models.training_sample import SampleCounts, SampleStatus, TrainingSample


class TrainingSampleRepository(Protocol):
    async def add(self, sample: TrainingSample) -> TrainingSample: ...

    async def get(self, sample_id: str) -> TrainingSample | None: ...

    async def update(self, sample: TrainingSample) -> None: ...

    async def counts(self) -> SampleCounts: ...

    async def list(
        self, status: SampleStatus | None = None, limit: int = 100
    ) -> builtins.list[TrainingSample]: ...
