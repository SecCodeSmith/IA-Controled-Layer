"""Deterministic hash-based sampler for reproducible sampling decisions."""
from hashlib import sha256


class HashSampler:
    """Sample deterministically based on hash of salt and key.

    Produces consistent results for the same salt and key across runs,
    allowing attackers to precompute skip patterns per salt.
    Used with a per-rule salt to prevent that.
    """

    def __init__(self, salt: str) -> None:
        """Initialize with a salt string."""
        self._salt = salt

    def should_sample(self, rate: float, key: str) -> bool:
        """Determine if a key should be sampled based on rate.

        Args:
            rate: Sampling rate [0, 1]. 0 never samples, 1 always samples.
            key: Unique key for this decision (e.g., "rule|point|text").

        Returns:
            True if the key should be sampled, False otherwise.
        """
        if rate <= 0.0:
            return False
        if rate >= 1.0:
            return True

        # Compute hash and convert to [0, 1) range
        hash_input = f"{self._salt}|{key}"
        hash_hex = sha256(hash_input.encode()).hexdigest()[:8]
        hash_int = int(hash_hex, 16)
        hash_fraction = hash_int / 0xFFFFFFFF

        return hash_fraction < rate
