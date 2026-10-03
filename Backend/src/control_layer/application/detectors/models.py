from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Match:
    kind: str
    start: int
    end: int
    value: str
