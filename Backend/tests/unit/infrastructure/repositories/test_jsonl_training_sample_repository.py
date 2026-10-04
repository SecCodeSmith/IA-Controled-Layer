"""Tests for JsonlTrainingSampleRepository."""

import asyncio
from datetime import datetime
from pathlib import Path

import pytest

from control_layer.domain.models.training_sample import (
    SampleStatus,
    TrainingSample,
)
from control_layer.infrastructure.repositories.jsonl_training_sample_repository import (
    JsonlTrainingSampleRepository,
)


@pytest.fixture
def sample1() -> TrainingSample:
    """Create a test sample."""
    return TrainingSample(
        id="s1",
        text="test prompt 1",
        label=1,
        source="judge",
        status=SampleStatus.pending,
        confidence=0.9,
        reason="test",
        tree_probability=0.7,
        point=None,
        call_id="call1",
        created_at=datetime.utcnow(),
        reviewed_by=None,
    )


@pytest.fixture
def sample2() -> TrainingSample:
    """Create another test sample."""
    return TrainingSample(
        id="s2",
        text="test prompt 2",
        label=0,
        source="judge",
        status=SampleStatus.accepted,
        confidence=0.8,
        reason="test",
        tree_probability=0.3,
        point=None,
        call_id="call2",
        created_at=datetime.utcnow(),
        reviewed_by="reviewer",
    )


@pytest.mark.asyncio
async def test_jsonl_repository_add_persists(tmp_path: Path) -> None:
    """Test that added samples are persisted to JSONL."""
    repo_path = tmp_path / "samples.jsonl"
    repo = JsonlTrainingSampleRepository(repo_path)

    sample = TrainingSample(
        id="s1",
        text="test text",
        label=1,
        source="judge",
        status=SampleStatus.pending,
        confidence=0.9,
        reason="test",
        tree_probability=0.7,
        point=None,
        call_id="call1",
        created_at=datetime.utcnow(),
        reviewed_by=None,
    )

    result = await repo.add(sample)
    assert result.id == sample.id
    assert repo_path.exists()


@pytest.mark.asyncio
async def test_jsonl_repository_dedupe_on_text_sha256(tmp_path: Path) -> None:
    """Test that samples with same text_sha256 are deduplicated."""
    repo_path = tmp_path / "samples.jsonl"
    repo = JsonlTrainingSampleRepository(repo_path)

    sample1 = TrainingSample(
        id="s1",
        text="same text",
        label=1,
        source="judge",
        status=SampleStatus.pending,
        confidence=0.9,
        reason="test",
        tree_probability=0.7,
        point=None,
        call_id="call1",
        created_at=datetime.utcnow(),
        reviewed_by=None,
    )

    sample2 = TrainingSample(
        id="s2",
        text="same text",
        label=0,
        source="judge",
        status=SampleStatus.pending,
        confidence=0.8,
        reason="different",
        tree_probability=0.5,
        point=None,
        call_id="call2",
        created_at=datetime.utcnow(),
        reviewed_by=None,
    )

    result1 = await repo.add(sample1)
    result2 = await repo.add(sample2)

    # Second add should return the existing sample
    assert result1.id == result2.id
    assert result1.id == "s1"


@pytest.mark.asyncio
async def test_jsonl_repository_update_persists(tmp_path: Path) -> None:
    """Test that updates are persisted."""
    repo_path = tmp_path / "samples.jsonl"
    repo = JsonlTrainingSampleRepository(repo_path)

    sample = TrainingSample(
        id="s1",
        text="test text",
        label=1,
        source="judge",
        status=SampleStatus.pending,
        confidence=0.9,
        reason="test",
        tree_probability=0.7,
        point=None,
        call_id="call1",
        created_at=datetime.utcnow(),
        reviewed_by=None,
    )

    await repo.add(sample)

    updated = sample.model_copy(update={"status": SampleStatus.accepted})
    await repo.update(updated)

    retrieved = await repo.get("s1")
    assert retrieved is not None
    assert retrieved.status == SampleStatus.accepted


@pytest.mark.asyncio
async def test_jsonl_repository_get(tmp_path: Path) -> None:
    """Test getting a sample by ID."""
    repo_path = tmp_path / "samples.jsonl"
    repo = JsonlTrainingSampleRepository(repo_path)

    sample = TrainingSample(
        id="s1",
        text="test text",
        label=1,
        source="judge",
        status=SampleStatus.pending,
        confidence=0.9,
        reason="test",
        tree_probability=0.7,
        point=None,
        call_id="call1",
        created_at=datetime.utcnow(),
        reviewed_by=None,
    )

    await repo.add(sample)
    retrieved = await repo.get("s1")

    assert retrieved is not None
    assert retrieved.id == "s1"
    assert retrieved.text == "test text"


@pytest.mark.asyncio
async def test_jsonl_repository_get_nonexistent(tmp_path: Path) -> None:
    """Test getting a nonexistent sample returns None."""
    repo_path = tmp_path / "samples.jsonl"
    repo = JsonlTrainingSampleRepository(repo_path)

    retrieved = await repo.get("nonexistent")
    assert retrieved is None


@pytest.mark.asyncio
async def test_jsonl_repository_list(tmp_path: Path) -> None:
    """Test listing samples."""
    repo_path = tmp_path / "samples.jsonl"
    repo = JsonlTrainingSampleRepository(repo_path)

    for i in range(5):
        sample = TrainingSample(
            id=f"s{i}",
            text=f"test text {i}",
            label=i % 2,
            source="judge",
            status=SampleStatus.pending if i < 3 else SampleStatus.accepted,
            confidence=0.9,
            reason="test",
            tree_probability=0.7,
            point=None,
            call_id=f"call{i}",
            created_at=datetime.utcnow(),
            reviewed_by=None,
        )
        await repo.add(sample)

    # List all
    all_samples = await repo.list(status=None, limit=100)
    assert len(all_samples) == 5

    # List pending only
    pending = await repo.list(status=SampleStatus.pending, limit=100)
    assert len(pending) == 3

    # List accepted only
    accepted = await repo.list(status=SampleStatus.accepted, limit=100)
    assert len(accepted) == 2


@pytest.mark.asyncio
async def test_jsonl_repository_list_limit(tmp_path: Path) -> None:
    """Test list respects limit."""
    repo_path = tmp_path / "samples.jsonl"
    repo = JsonlTrainingSampleRepository(repo_path)

    for i in range(10):
        sample = TrainingSample(
            id=f"s{i}",
            text=f"test {i}",
            label=0,
            source="judge",
            status=SampleStatus.pending,
            confidence=0.9,
            reason="test",
            tree_probability=0.7,
            point=None,
            call_id=f"call{i}",
            created_at=datetime.utcnow(),
            reviewed_by=None,
        )
        await repo.add(sample)

    results = await repo.list(status=None, limit=3)
    assert len(results) == 3


@pytest.mark.asyncio
async def test_jsonl_repository_counts(tmp_path: Path) -> None:
    """Test getting sample counts."""
    repo_path = tmp_path / "samples.jsonl"
    repo = JsonlTrainingSampleRepository(repo_path)

    for i in range(5):
        sample = TrainingSample(
            id=f"s{i}",
            text=f"test {i}",
            label=0,
            source="judge",
            status=[SampleStatus.pending, SampleStatus.accepted, SampleStatus.rejected][i % 3],
            confidence=0.9,
            reason="test",
            tree_probability=0.7,
            point=None,
            call_id=f"call{i}",
            created_at=datetime.utcnow(),
            reviewed_by=None,
        )
        await repo.add(sample)

    counts = await repo.counts()
    assert counts.pending >= 1
    assert counts.accepted >= 1
    assert counts.rejected >= 1
    assert counts.total == 5


@pytest.mark.asyncio
async def test_jsonl_repository_fresh_instance_loads_from_file(
    tmp_path: Path,
) -> None:
    """Test that a fresh instance loads samples from the file."""
    repo_path = tmp_path / "samples.jsonl"

    # Add a sample with first repo instance
    repo1 = JsonlTrainingSampleRepository(repo_path)
    sample = TrainingSample(
        id="s1",
        text="test text",
        label=1,
        source="judge",
        status=SampleStatus.pending,
        confidence=0.9,
        reason="test",
        tree_probability=0.7,
        point=None,
        call_id="call1",
        created_at=datetime.utcnow(),
        reviewed_by=None,
    )
    await repo1.add(sample)

    # Create fresh instance and verify it loads the sample
    repo2 = JsonlTrainingSampleRepository(repo_path)
    retrieved = await repo2.get("s1")

    assert retrieved is not None
    assert retrieved.text == "test text"


@pytest.mark.asyncio
async def test_jsonl_repository_concurrent_adds(tmp_path: Path) -> None:
    """Test concurrent adds don't lose data."""
    repo_path = tmp_path / "samples.jsonl"
    repo = JsonlTrainingSampleRepository(repo_path)

    async def add_sample(i: int) -> None:
        sample = TrainingSample(
            id=f"s{i}",
            text=f"test {i}",
            label=i % 2,
            source="judge",
            status=SampleStatus.pending,
            confidence=0.9,
            reason="test",
            tree_probability=0.7,
            point=None,
            call_id=f"call{i}",
            created_at=datetime.utcnow(),
            reviewed_by=None,
        )
        await repo.add(sample)

    await asyncio.gather(*[add_sample(i) for i in range(10)])

    all_samples = await repo.list(status=None, limit=100)
    assert len(all_samples) == 10
