"""Async JSONL-based training sample repository."""
import asyncio
import json
from pathlib import Path

from control_layer.domain.models.training_sample import (
    SampleCounts,
    SampleStatus,
    TrainingSample,
)


class JsonlTrainingSampleRepository:
    """Store and retrieve training samples in a JSONL file.

    Implements the TrainingSampleRepository port.
    In-memory dict keyed by id, loaded from file on first use.
    append-only file, last-write-wins by id on reload.
    """

    def __init__(self, path: Path) -> None:
        """Initialize with a file path."""
        self._path = Path(path)
        self._samples: dict[str, TrainingSample] | None = None
        self._lock = asyncio.Lock()

    async def _ensure_loaded(self) -> None:
        """Load samples from file if not already loaded."""
        if self._samples is not None:
            return

        async with self._lock:
            if self._samples is not None:
                return

            self._samples = {}
            if self._path.exists():
                await asyncio.to_thread(self._load_from_file)

    def _load_from_file(self) -> None:
        """Load samples from JSONL file (called in thread)."""
        if not self._path.exists():
            return

        assert self._samples is not None
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                sample = TrainingSample.model_validate(data)
                self._samples[sample.id] = sample

    async def add(self, sample: TrainingSample) -> TrainingSample:
        """Add or deduplicate a training sample.

        If a sample with the same text_sha256 already exists and has
        status pending or accepted, return the existing one.
        Otherwise, add the new sample and return it.
        """
        await self._ensure_loaded()
        assert self._samples is not None

        # Check for duplicates by text_sha256 among pending/accepted
        for existing in self._samples.values():
            if (
                existing.text_sha256 == sample.text_sha256
                and existing.status in (SampleStatus.pending, SampleStatus.accepted)
            ):
                return existing

        # Add new sample
        self._samples[sample.id] = sample
        await asyncio.to_thread(self._append_to_file, sample)
        return sample

    def _append_to_file(self, sample: TrainingSample) -> None:
        """Append a sample to the JSONL file (called in thread)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as f:
            line = json.dumps(sample.model_dump(mode="json"), ensure_ascii=False)
            f.write(line + "\n")

    async def get(self, sample_id: str) -> TrainingSample | None:
        """Get a sample by ID."""
        await self._ensure_loaded()
        assert self._samples is not None
        return self._samples.get(sample_id)

    async def update(self, sample: TrainingSample) -> None:
        """Update a sample.

        Appends the updated sample to the file.
        On reload, the last version of each id is used.
        """
        await self._ensure_loaded()
        assert self._samples is not None

        self._samples[sample.id] = sample
        await asyncio.to_thread(self._append_to_file, sample)

    async def list(
        self, status: SampleStatus | None = None, limit: int = 100
    ) -> list[TrainingSample]:
        """List samples, optionally filtered by status.

        Returns the most recent samples first (LIFO by addition order).
        """
        await self._ensure_loaded()
        assert self._samples is not None

        samples = list(self._samples.values())

        if status is not None:
            samples = [s for s in samples if s.status == status]

        # Reverse to get newest first
        samples.reverse()

        return samples[:limit]

    async def counts(self) -> SampleCounts:
        """Get sample counts by status."""
        await self._ensure_loaded()
        assert self._samples is not None

        pending = sum(
            1 for s in self._samples.values() if s.status == SampleStatus.pending
        )
        accepted = sum(
            1 for s in self._samples.values() if s.status == SampleStatus.accepted
        )
        rejected = sum(
            1 for s in self._samples.values() if s.status == SampleStatus.rejected
        )

        return SampleCounts(pending=pending, accepted=accepted, rejected=rejected)
