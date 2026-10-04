"""Tests for HashSampler deterministic sampling."""

from control_layer.infrastructure.ml.hash_sampler import HashSampler


def test_hash_sampler_rate_zero_never_samples() -> None:
    """Rate 0 should never sample."""
    sampler = HashSampler("test-salt")
    assert not sampler.should_sample(0.0, "any-key")
    assert not sampler.should_sample(0.0, "another-key")


def test_hash_sampler_rate_one_always_samples() -> None:
    """Rate 1 should always sample."""
    sampler = HashSampler("test-salt")
    assert sampler.should_sample(1.0, "any-key")
    assert sampler.should_sample(1.0, "another-key")


def test_hash_sampler_deterministic() -> None:
    """Same salt and key should always produce same result."""
    sampler1 = HashSampler("salt-1")
    sampler2 = HashSampler("salt-1")

    result1a = sampler1.should_sample(0.5, "key-1")
    result1b = sampler1.should_sample(0.5, "key-1")
    result2 = sampler2.should_sample(0.5, "key-1")

    assert result1a == result1b == result2


def test_hash_sampler_different_salt_different_result() -> None:
    """Different salts should produce different results for the same key."""
    sampler1 = HashSampler("salt-1")
    sampler2 = HashSampler("salt-2")

    results1 = set()
    results2 = set()

    for i in range(20):
        results1.add(sampler1.should_sample(0.5, f"key-{i}"))
        results2.add(sampler2.should_sample(0.5, f"key-{i}"))

    # Both should have both True and False (with high probability)
    assert len(results1) == 2
    assert len(results2) == 2


def test_hash_sampler_rate_distribution() -> None:
    """Rate ≈0.2 should sample approximately 20% of keys."""
    sampler = HashSampler("test-salt")

    samples = sum(1 for i in range(2000) if sampler.should_sample(0.2, f"key-{i}"))
    rate = samples / 2000

    # Should be approximately 20%, allow ±5%
    assert 0.15 < rate < 0.25, f"Expected rate ~0.2, got {rate:.3f}"


def test_hash_sampler_rate_boundaries() -> None:
    """Test rates between 0 and 1."""
    sampler = HashSampler("boundary-test")

    # Very low rate
    low_samples = sum(1 for i in range(1000) if sampler.should_sample(0.05, f"low-{i}"))
    assert low_samples < 100  # Should be around 50, definitely less than 100

    # Very high rate
    high_samples = sum(1 for i in range(1000) if sampler.should_sample(0.95, f"high-{i}"))
    assert high_samples > 900  # Should be around 950, definitely more than 900
