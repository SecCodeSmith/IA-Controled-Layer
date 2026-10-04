from __future__ import annotations

from typing import Protocol


class Sampler(Protocol):
    def should_sample(self, rate: float, key: str) -> bool: ...
