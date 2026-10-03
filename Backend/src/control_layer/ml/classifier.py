from pathlib import Path

import joblib
import numpy as np


class SklearnPromptClassifier:
    def __init__(self, pipeline: object, path: str) -> None:
        self._pipeline = pipeline
        self._path = path

    @classmethod
    def load(cls, path: str) -> "SklearnPromptClassifier":
        resolved = Path(path)
        if not resolved.exists():
            raise FileNotFoundError(f"classifier artifact not found: {path}")
        pipeline = joblib.load(resolved)
        return cls(pipeline=pipeline, path=path)

    def predict_proba(self, text: str) -> float:
        probabilities = self._pipeline.predict_proba([text])[0]
        classes = list(self._pipeline.classes_)
        index = classes.index(1)
        return float(np.clip(probabilities[index], 0.0, 1.0))

    def info(self) -> dict[str, object]:
        return {"loaded": True, "path": self._path}


class NullPromptClassifier:
    def predict_proba(self, text: str) -> float:
        return 0.0

    def info(self) -> dict[str, object]:
        return {"loaded": False, "path": None}
