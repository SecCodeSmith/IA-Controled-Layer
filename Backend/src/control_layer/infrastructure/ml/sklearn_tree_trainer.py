import json
import os
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import joblib

from control_layer.domain.models.classifier import TrainedModel
from control_layer.domain.models.training_sample import TrainingSample
from control_layer.ml.classifier import SklearnPromptClassifier
from control_layer.ml.dataset_schema import DatasetRow
from control_layer.ml.train import _load_dataset, train_with_feedback


class SklearnTreeTrainer:
    def __init__(
        self,
        base_csv: Path,
        supplement_csv: Path,
        artifact_path: Path,
        min_f1: float,
    ) -> None:
        self._base_csv = Path(base_csv)
        self._supplement_csv = Path(supplement_csv)
        self._artifact_path = Path(artifact_path)
        self._min_f1 = min_f1

    def train(self, feedback: Sequence[TrainingSample], *, seed: int) -> TrainedModel:
        base_rows = _load_dataset(self._base_csv)

        supplement_rows = _load_dataset(self._supplement_csv)

        feedback_rows = [
            DatasetRow(
                text=sample.text,
                label=sample.label,
                category="judge",
            )
            for sample in feedback
        ]

        all_feedback = supplement_rows + feedback_rows

        pipeline, f1 = train_with_feedback(
            base_rows,
            all_feedback,
            model="tree",
            seed=seed,
            verbose=False,
        )

        return TrainedModel(
            estimator=pipeline,
            model_type="tree",
            f1=f1,
            n_base=len(base_rows),
            n_feedback=len(all_feedback),
            trained_at=datetime.utcnow(),
        )

    def publish(self, model: TrainedModel, *, version: int) -> SklearnPromptClassifier:
        self._artifact_path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = self._artifact_path.with_suffix(".joblib.tmp")
        joblib.dump(model.estimator, tmp_path)

        os.replace(tmp_path, self._artifact_path)

        # Write metadata last (so it only exists if joblib write succeeded)
        meta_path = self._artifact_path.with_suffix(".joblib.meta.json")
        meta = {
            "model_type": model.model_type,
            "trained_at": model.trained_at.isoformat() + "Z",
            "f1": model.f1,
            "n_base": model.n_base,
            "n_feedback": model.n_feedback,
            "version": version,
        }
        with meta_path.open("w", encoding="utf-8") as f:
            json.dump(meta, f)

        return SklearnPromptClassifier.load(str(self._artifact_path))
