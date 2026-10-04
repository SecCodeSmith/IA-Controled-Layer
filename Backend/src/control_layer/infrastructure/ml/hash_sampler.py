from hashlib import sha256


class HashSampler:
    def __init__(self, salt: str) -> None:
        self._salt = salt

    def should_sample(self, rate: float, key: str) -> bool:
        if rate <= 0.0:
            return False
        if rate >= 1.0:
            return True

        hash_input = f"{self._salt}|{key}"
        hash_hex = sha256(hash_input.encode()).hexdigest()[:8]
        hash_int = int(hash_hex, 16)
        hash_fraction = hash_int / 0xFFFFFFFF

        return hash_fraction < rate
