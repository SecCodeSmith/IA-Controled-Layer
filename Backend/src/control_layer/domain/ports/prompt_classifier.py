from __future__ import annotations

from typing import Protocol


class PromptClassifier(Protocol):
    def predict_proba(self, text: str) -> float: ...
