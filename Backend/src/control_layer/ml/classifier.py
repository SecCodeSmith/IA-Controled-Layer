import json
from functools import cached_property
from pathlib import Path

import joblib
import numpy as np
from pydantic import ValidationError
from sklearn.tree import DecisionTreeClassifier

from control_layer.domain.models.classifier import (
    ClassifierExplanation,
    ClassifierInfo,
    LeafInfo,
    PathStep,
)

_TREE_MODEL_TYPE = "tree"
_TOP_FEATURE_COUNT = 5
_POSITIVE_CLASS = 1


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
        tree = self._tree
        if tree is None:
            return self._estimator_probability(text)
        return _smoothed(self._leaf(tree, self._features(text)))

    def explain(self, text: str) -> ClassifierExplanation:
        tree = self._tree
        if tree is None:
            return ClassifierExplanation(
                probability=self.predict_proba(text), model_type=self._model_type
            )
        features = self._features(text)
        leaf = self._leaf(tree, features)
        path = self._decision_path(tree, features)
        return ClassifierExplanation(
            probability=_smoothed(leaf),
            model_type=_TREE_MODEL_TYPE,
            path=[step for step, _ in path],
            leaf=leaf,
            top_features=_top_features(tree, path),
        )

    def describe(self) -> ClassifierInfo:
        meta = self._read_meta()
        try:
            return self._info(meta)
        except ValidationError:
            return self._info({})

    def info(self) -> dict[str, object]:
        return {"loaded": True, "path": self._path}

    @cached_property
    def _tree(self) -> DecisionTreeClassifier | None:
        estimator = self._estimator
        return estimator if isinstance(estimator, DecisionTreeClassifier) else None

    @cached_property
    def _estimator(self) -> object | None:
        steps = getattr(self._pipeline, "named_steps", None)
        return steps.get("clf") if steps is not None else None

    @cached_property
    def _model_type(self) -> str:
        if self._tree is not None:
            return _TREE_MODEL_TYPE
        return type(self._estimator or self._pipeline).__name__

    @cached_property
    def _feature_names(self) -> np.ndarray:
        return self._pipeline.named_steps["features"].get_feature_names_out()

    def _estimator_probability(self, text: str) -> float:
        probabilities = self._pipeline.predict_proba([text])[0]
        index = list(self._pipeline.classes_).index(_POSITIVE_CLASS)
        return float(np.clip(probabilities[index], 0.0, 1.0))

    def _features(self, text: str) -> object:
        return self._pipeline.named_steps["features"].transform([text])

    @staticmethod
    def _leaf(tree: DecisionTreeClassifier, features: object) -> LeafInfo:
        node_id = int(tree.apply(features)[0])
        index = list(tree.classes_).index(_POSITIVE_CLASS)
        fraction = float(np.clip(tree.tree_.value[node_id][0][index], 0.0, 1.0))
        return LeafInfo(
            node_id=node_id,
            samples=int(tree.tree_.n_node_samples[node_id]),
            positive_fraction=fraction,
        )

    def _decision_path(
        self, tree: DecisionTreeClassifier, features: object
    ) -> list[tuple[PathStep, int]]:
        structure = tree.tree_
        steps: list[tuple[PathStep, int]] = []
        for node_id in tree.decision_path(features).indices:
            feature_index = int(structure.feature[node_id])
            if feature_index < 0:
                continue
            value = float(features[0, feature_index])
            threshold = float(structure.threshold[node_id])
            step = PathStep(
                feature=str(self._feature_names[feature_index]),
                value=value,
                threshold=threshold,
                direction="<=" if value <= threshold else ">",
            )
            steps.append((step, feature_index))
        return steps

    def _read_meta(self) -> dict:
        try:
            meta = json.loads(Path(f"{self._path}.meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return meta if isinstance(meta, dict) else {}

    def _info(self, meta: dict) -> ClassifierInfo:
        return ClassifierInfo(
            loaded=True,
            path=self._path,
            model_type=meta.get("model_type", self._model_type),
            version=meta.get("version", 0),
            trained_at=meta.get("trained_at"),
            f1=meta.get("f1"),
            n_base=meta.get("n_base", 0),
            n_feedback=meta.get("n_feedback", 0),
        )


def _smoothed(leaf: LeafInfo) -> float:
    return (leaf.positive_fraction * leaf.samples + 1) / (leaf.samples + 2)


def _top_features(tree: DecisionTreeClassifier, path: list[tuple[PathStep, int]]) -> list[str]:
    importances = tree.feature_importances_
    ranked: dict[str, float] = {}
    for step, feature_index in path:
        ranked[step.feature] = float(importances[feature_index])
    ordered = sorted(ranked, key=ranked.__getitem__, reverse=True)
    return ordered[:_TOP_FEATURE_COUNT]


class NullPromptClassifier:
    def predict_proba(self, text: str) -> float:
        return 0.0

    def explain(self, text: str) -> ClassifierExplanation:
        return ClassifierExplanation(probability=0.0, model_type="null")

    def describe(self) -> ClassifierInfo:
        return ClassifierInfo(loaded=False)

    def info(self) -> dict[str, object]:
        return {"loaded": False, "path": None}
